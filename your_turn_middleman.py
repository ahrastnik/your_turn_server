import struct
from typing import Callable

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT

YOUR_TURN_IP: str = "127.0.0.1"


class YourTurnMiddlemanInterface(DatagramProtocol):
    def __init__(self, recv_callback: Callable, id: int = -1, port: int = 0) -> None:
        super().__init__()
        self._id = id
        self._port: int = port
        self._recv_callback: Callable = recv_callback
    
    def get_port(self) -> int:
        return self._port
    
    def datagramReceived(self, data: bytes, addr: tuple) -> None:
        self._recv_callback(self._id, data, addr)


class YourTurnMiddleman:
    PACKET_PREFIX = 0xAA
    PORT_RANGE_START: int = 6970
    PEERS_MAX: int = 12  # TODO: Implement peer limit

    def __init__(self, peer_id: int = -1) -> None:
        self.relay = YourTurnMiddlemanInterface(self._received_from_relay)
        self._peers: dict = {}
        self._next_peer_port: int = YourTurnMiddleman.PORT_RANGE_START
        self.register_peer(1)

    def _received_from_relay(self, peer_id: int, turn_packet: bytes, addr: tuple) -> None:
        print(f"received {turn_packet.hex()} from {addr}")
        parsed_turn_packet = self._parse_turn_packet(turn_packet)
        if parsed_turn_packet == ():
            print("Failed to parse TURN packet")
            return
        peer_id, enet_packet = parsed_turn_packet
        
        peer = self._peers.get(peer_id, None)
        if peer is None:
            peer = self.register_peer(peer_id)
        
        # Forward received data to peer
        peer.transport.write(enet_packet, ("127.0.0.1", peer.get_port()))
    
    def _received_from_peer(self, peer_id: int, enet_packet: bytes, addr: tuple) -> None:
        print(f"received {enet_packet.hex()} from {addr}")
        turn_packet: bytes = self._make_turn_packet(peer_id, enet_packet)
        # Forward received data to relay server
        self.relay.transport.write(turn_packet, (YOUR_TURN_IP, YOUR_TURN_PORT))
    
    def register_peer(self, peer_id: int) -> YourTurnMiddlemanInterface:
        if peer_id <= 0 or peer_id in self._peers:
            return
        
        peer_port = self._next_peer_port
        peer = YourTurnMiddlemanInterface(self._received_from_peer, id=peer_id, port=peer_port)
        self._peers[peer_id] = peer
        reactor.listenUDP(peer_port, peer)
        self._next_peer_port += 1
        print(f"Peer interface registered at port {peer_port}")
        return peer
    
    # def unregister_peer(self, peer_id: int) -> None:
    #     # TODO: Implement
    #     # TODO: Handle starting/stopping listeners
    #     pass

    def _parse_turn_packet(self, turn_packet: bytes) -> bytes:
        # Packet structure: UDP<TURN<prefix: uint16, sender id: uint32, ENet packet>>
        # TODO: Strip address from received data
        # TODO: Compare received id with assigned one
        if len(turn_packet) <= 6:
            return ()
        
        preamble = struct.unpack(">HL", turn_packet[:6])
        prefix, sender_id = preamble
        if prefix != YourTurnMiddleman.PACKET_PREFIX:
            return ()
        
        return (sender_id, turn_packet[6:])

    def _make_turn_packet(self, id: int, enet_packet: bytes) -> bytes:
        preamble: bytes = struct.pack(">HL", YourTurnMiddleman.PACKET_PREFIX, id)
        return preamble + enet_packet
    
    def run(self):
        reactor.listenUDP(0, self.relay)
        reactor.run()


if __name__ == '__main__':
    middleman = YourTurnMiddleman()
    middleman.run()
