import argparse
import struct
from time import time
from typing import Callable

from twisted.internet import reactor, task
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6969

# Packet structure: UDP<TURN<prefix: uint16, sender/receiver id: uint32, Payload>>
# When registering by having no data inside Payload field
# the ID field represents the sender, if there is data in the Payload, then the ID represents the receiver
TURN_MSG_PREFIX: int = 0xAA
TURN_MSG_PREAMBLE_LEN: int = 6


def parse_turn_packet(turn_packet: bytes) -> tuple:
    # TODO: Verify sender id is valid
    if len(turn_packet) < TURN_MSG_PREAMBLE_LEN:
        return ()
    
    preamble = struct.unpack(">HL", turn_packet[:TURN_MSG_PREAMBLE_LEN])
    prefix, peer_id = preamble
    if prefix != TURN_MSG_PREFIX:
        return ()
    
    return peer_id, turn_packet[TURN_MSG_PREAMBLE_LEN:]


def make_turn_packet(id: int, payload: bytes = b"") -> bytes:
    preamble: bytes = struct.pack(">HL", TURN_MSG_PREFIX, id)
    return preamble + payload


class YourTurnPeer:
    STALE_TIME: float = 1.0  # [s]

    def __init__(self, ip: str, port: int, send_function: Callable, is_server: bool = False) -> None:
        self._ip: str = ip
        self._port: int = port
        self._send: Callable = send_function  # Transport Function through which to send data to peer
        self._is_server = is_server

        self._last_packet: float = 0  # [s] When was the last packet sent

    def is_server(self) -> bool:
        return self._is_server

    def get_addr(self) -> tuple:
        return (self._ip, self._port)
    
    def is_stale(self) -> bool:
        return (time() - self._last_packet) > YourTurnPeer.STALE_TIME
    
    def send(self, data: bytes) -> None:
        # Record sent message time
        self._last_packet = time()
        self._send(data, self.get_addr())


class YourTurnRelay(DatagramProtocol):
    KEEP_ALIVE_PERIOD: float = 1.0  # [s]

    def __init__(self, direct_mode: bool, verbose: bool = False) -> None:
        super().__init__()

        self._direct_mode: bool = direct_mode
        self._verbose: bool = verbose

        self._peer_map: dict = {}
        self._client_port_map: dict = {}
        # TODO: Cache server peer - self._peer_server: YourTurnPeer = None
        # This function is called periodically to make sure all peer connections stay alive
        self._keep_alive = task.LoopingCall(self._watchdog)
        self._keep_alive.start(YourTurnRelay.KEEP_ALIVE_PERIOD, now=True)
        # TODO: Implement optimized client transfer, by using a separate port for clients and avoiding packet parsing
        # TODO: Lease server/client registration for a limited time if no data flow is detected

    def _watchdog(self) -> None:
        for peer_id in self._peer_map:
            peer: YourTurnPeer = self._peer_map[peer_id]
            if not peer.is_stale():
                continue
            peer.send(make_turn_packet(peer_id))

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
        # Attempt to parse package
        parsed_packet = parse_turn_packet(data)
        if parsed_packet == ():
            if self._direct_mode:
                server_peer: YourTurnPeer = self._peer_map.get(1, None)
                if server_peer is None:
                    return
                
                client_peer: YourTurnPeer = self._client_port_map.get(sender_port, None)
                if client_peer is None:
                    self._client_port_map[sender_port] = YourTurnPeer(sender_ip, sender_port, self.transport.write)
                    server_peer.send(make_turn_packet(sender_port))
                    print(f"Client [{sender_port}:{sender_ip}] registered")

                server_peer.send(make_turn_packet(sender_port, data))
            else:
                print("Invalid packet received!")
            return
        
        peer_id, payload = parsed_packet
        
        if len(payload) <= 0:
            self.register_peer(peer_id, addr)
        else:
            if self._direct_mode:
                # Peer ID == Client port, when using direct mode
                client_peer: YourTurnPeer = self._client_port_map.get(peer_id, None)
                if client_peer is None:
                    return
                client_peer.send(payload)
                return

            peer: YourTurnPeer = self._peer_map.get(peer_id, None)
            if peer is None:
                print(f"Invalid peer ID {peer_id}")
                return
            
            if self._verbose:
                peer_ip, peer_port = peer.get_addr()
                print(f"{sender_ip}:{sender_port}\t-> {peer_ip}:{peer_port}")
            
            if peer_id != 1:
                peer.send(data)
            else:
                sender_id = self.get_peer_id_by_addr(addr)
                if sender_id <= 0:
                    print("Sender not yet registered!")
                    return
                peer.send(make_turn_packet(sender_id, payload))
    
    def register_peer(self, id: int, registerer_addr: tuple) -> None:
        # TODO: Disallow reregistration if id lease is still valid
        is_registered: bool = id in self._peer_map
        # Server doesn't need to know about it's own registration
        if id != 1:
            # Notify server of the registered peer
            server: YourTurnPeer = self._peer_map.get(1, None)
            if server is None:
                print("Server not yet registered!")
                return
            server.send(make_turn_packet(id))
        
        ip, port = registerer_addr
        print(f"Peer {id}[{ip}:{port}] {'re-' if is_registered else ''}registered")
        peer = YourTurnPeer(ip, port, self.transport.write)
        self._peer_map[id] = peer
        # Confirm registration by echoing back
        # NOTE: This mostly servers as a connection-confirmation package, as some routers will drop the
        # connection if no data is received back within a given time-frame
        peer.send(make_turn_packet(id))
    
    # def unregister_peer(peer_id: int) -> None:
    #     pass


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        prog="Your TURN server",
        description="Your TURN (Traversal Using Relays around NAT) server"
    )
    arg_parser.add_argument("-p", "--port", type=int, default=YOUR_TURN_PORT)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    arg_parser.add_argument("-d", "--direct", action="store_true")
    args = arg_parser.parse_args()

    reactor.listenUDP(args.port, YourTurnRelay(args.direct, verbose=args.verbose))
    print(f"Started TURN server on port {args.port}")
    reactor.run()
