import struct
from typing import Callable

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from your_turn import (
    YOUR_TURN_PORT,
    parse_turn_packet,
    make_turn_packet,
)

YOUR_TURN_IP: str = "127.0.0.1"


class YourTurnMiddlemanInterface(DatagramProtocol):
    def __init__(self, id: int, recv_callback: Callable, port: int = 0) -> None:
        super().__init__()

        self._id: int = id
        self._port: int = port
        self._recv_callback: Callable = recv_callback
    
    def get_port(self) -> int:
        return self._port

    def datagramReceived(self, data: bytes, addr: tuple) -> None:
        self._recv_callback(self._id, data, addr)


class YourTurnMiddlemanRelay(YourTurnMiddlemanInterface):
    def startProtocol(self):
        self.transport.connect(YOUR_TURN_IP, YOUR_TURN_PORT)
        # Register interface on TURN server
        self.transport.write(make_turn_packet(self._id))


class YourTurnMiddlemanPeer(YourTurnMiddlemanInterface):
    def startProtocol(self):
        self.transport.connect("127.0.0.1", self._port)


class YourTurnMiddleman:
    PORT_RANGE_START: int = 6970
    # TODO: Implement peer limit
    # PEERS_MAX: int = 12

    def __init__(self, id: int = 1) -> None:
        self._id = id
        self.relay = YourTurnMiddlemanRelay(id, self._received_from_relay)
        self._peers: dict = {}
        self._next_peer_port: int = YourTurnMiddleman.PORT_RANGE_START
        self.register_peer(1)

    def _received_from_relay(self, peer_id: int, turn_packet: bytes, addr: tuple) -> None:
        print(f"received {turn_packet.hex()} from {addr}")
        parsed_turn_packet = parse_turn_packet(turn_packet)
        if parsed_turn_packet == ():
            print("Failed to parse TURN packet")
            return
        peer_id, enet_packet = parsed_turn_packet
        
        peer = self._peers.get(peer_id, None)
        if peer is None:
            peer = self.register_peer(peer_id)
        
        # Forward received data to peer
        peer.transport.write(enet_packet)
    
    def _received_from_peer(self, peer_id: int, enet_packet: bytes, addr: tuple) -> None:
        print(f"received {enet_packet.hex()} from {addr}")
        turn_packet: bytes = make_turn_packet(peer_id, enet_packet)
        # Forward received data to relay server
        self.relay.transport.write(turn_packet)
    
    def register_peer(self, peer_id: int) -> YourTurnMiddlemanPeer:
        if peer_id <= 0 or peer_id in self._peers:
            return
        
        peer_port = self._next_peer_port
        peer = YourTurnMiddlemanPeer(peer_id, self._received_from_peer, port=peer_port)
        self._peers[peer_id] = peer
        reactor.listenUDP(peer_port, peer)
        self._next_peer_port += 1
        print(f"Peer interface registered at port {peer_port}")
        return peer
    
    # def unregister_peer(self, peer_id: int) -> None:
    #     # TODO: Implement
    #     # TODO: Handle starting/stopping listeners
    #     pass
    
    def run(self):
        reactor.listenUDP(0, self.relay)
        reactor.run()


if __name__ == '__main__':
    middleman = YourTurnMiddleman()
    middleman.run()
