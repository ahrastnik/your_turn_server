import argparse
import struct
from dataclasses import dataclass

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6942

# Packet structure: UDP<TURN<prefix: uint16, sender/receiver id: uint32, Payload>>
# When registering by having no data inside Payload field
# the ID field represents the sender, if there is data in the Payload, then the ID represents the receiver
TURN_MSG_PREFIX: int = 0xAA
TURN_MSG_PREAMBLE_LEN: int = 6


def parse_turn_packet(turn_packet: bytes) -> bytes:
    # TODO: Verify sender id is valid
    if len(turn_packet) < TURN_MSG_PREAMBLE_LEN:
        return ()
    
    preamble = struct.unpack(">HL", turn_packet[:TURN_MSG_PREAMBLE_LEN])
    prefix, peer_id = preamble
    if prefix != TURN_MSG_PREFIX:
        return ()
    
    return (peer_id, turn_packet[TURN_MSG_PREAMBLE_LEN:])


def make_turn_packet(id: int, payload: bytes = b"") -> bytes:
    preamble: bytes = struct.pack(">HL", TURN_MSG_PREFIX, id)
    return preamble + payload


@dataclass
class YourTurnPeer:
    ip: str
    port: int

    def get_addr(self) -> tuple:
        return (self.ip, self.port)


class YourTurnRelay(DatagramProtocol):
    def __init__(self, verbose: bool = False) -> None:
        super().__init__()

        self._verbose: bool = verbose

        self._peer_map: dict = {}
        # TODO: Implement optimized client transfer, by using a separate port for clients and avoiding packet parsing
        # TODO: Lease server/client registration for a limited time if no data flow is detected

    def get_peer_id_by_addr(self, addr: tuple) -> int:
        for peer_id in self._peer_map:
            peer = self._peer_map[peer_id]
            if peer.get_addr() == addr:
                return peer_id
        return -1

    def datagramReceived(self, data, addr) -> None:
        if self._verbose:
            print(f"received {data.hex()} from {addr}")
        
        sender_ip, sender_port = addr
        parsed_packet = parse_turn_packet(data)
        if parsed_packet == ():
            print("Invalid packet received!")
            return
        peer_id, payload = parsed_packet
        
        if len(payload) <= 0:
            self.register_peer(peer_id, sender_ip, sender_port)
        else:
            peer: YourTurnPeer = self._peer_map.get(peer_id, None)
            if peer is None:
                print(f"Invalid peer ID {peer_id}")
                return
            
            if self._verbose:
                print(f"{sender_ip}:{sender_port}\t-> {peer.ip}:{peer.port}")
            
            if peer_id != 1:
                self.transport.write(data, peer.get_addr())
            else:
                sender_id = self.get_peer_id_by_addr(addr)
                if sender_id <= 0:
                    print("Sender not yet registered!")
                    return
                self.transport.write(make_turn_packet(sender_id, payload), peer.get_addr())
    
    def register_peer(self, id: int, ip: str, port: int) -> None:
        # TODO: Disallow reregistration if id lease is still valid
        is_registered: bool = id in self._peer_map
        # Server doesn't need to know about it's own registration
        if id != 1:
            # Notify server of the registered peer
            server: YourTurnPeer = self._peer_map.get(1, None)
            if server is None:
                print("Server not yet registered!")
                return
            self.transport.write(make_turn_packet(id), server.get_addr())
        
        print(f"Peer {id}[{ip}:{port}] {'re-' if is_registered else ''}registered")
        self._peer_map[id] = YourTurnPeer(ip, port)
    
    # def unregister_peer(peer_id: int) -> None:
    #     pass


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        prog="Your TURN server",
        description="Your TURN (Traversal Using Relays around NAT) server"
    )
    arg_parser.add_argument("-p", "--port", type=int, default=YOUR_TURN_PORT)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    args = arg_parser.parse_args()

    reactor.listenUDP(args.port, YourTurnRelay(verbose=args.verbose))
    print(f"Started TURN server on port {args.port}")
    reactor.run()
