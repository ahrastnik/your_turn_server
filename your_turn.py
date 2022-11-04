import struct
from dataclasses import dataclass

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6942

# Packet structure: UDP<TURN<prefix: uint16, sender/receiver id: uint32, ENet packet>>
# When registering by having no data inside ENet packet field
# the ID field represents the sender, if there is data in the ENet packet, then the ID represents the receiver
TURN_MSG_PREFIX: int = 0xAA
TURN_MSG_PREAMBLE_LEN: int = 6


def parse_turn_packet(turn_packet: bytes) -> bytes:
    # Packet structure: UDP<TURN<prefix: uint16, sender id: uint32, ENet packet>>
    # TODO: Strip address from received data
    # TODO: Verify sender id is valid
    if len(turn_packet) < TURN_MSG_PREAMBLE_LEN:
        return ()
    
    preamble = struct.unpack(">HL", turn_packet[:TURN_MSG_PREAMBLE_LEN])
    prefix, peer_id = preamble
    if prefix != TURN_MSG_PREFIX:
        return ()
    
    return (peer_id, turn_packet[TURN_MSG_PREAMBLE_LEN:])


def make_turn_packet(id: int, enet_packet: bytes = b"") -> bytes:
    preamble: bytes = struct.pack(">HL", TURN_MSG_PREFIX, id)
    return preamble + enet_packet


@dataclass
class YourTurnPeer:
    ip: str
    port: int

    def get_addr(self) -> tuple:
        return (self.ip, self.port)


class YourTurnRelay(DatagramProtocol):
    def __init__(self) -> None:
        super().__init__()
        # TODO: Implement optimized client transfer, by using a separate port for clients and avoiding packet parsing
        # TODO: Lease server/client registration for a limited time if no data flow is detected
        self._server_ip: str = ""
        self._server_port: int = 0
        # TODO: Add support for multiple clients
        self._client_ip: str = ""
        self._client_port: str = 0

        self._peer_map: dict = {}

    def get_server_address(self) -> tuple:
        return (self._server_ip, self._server_port)
    
    def is_server(self, addr: tuple) -> bool:
        host, port = addr
        return host == self._server_ip and port == self._server_port
    
    def is_address_valid(self, addr: tuple) -> bool:
        host, port = addr
        return host != "" and port != 0
    
    def get_client_address(self) -> tuple:
        return (self._client_ip, self._client_port)
    
    def is_client(self, addr: tuple) -> bool:
        host, port = addr
        return host == self._client_ip and port == self._client_port

    def is_relay_linked(self) -> bool:
        """Are server and client linked?"""
        return self._server_ip != ""

    def datagramReceived(self, data, addr) -> None:
        print(f"received {data.hex()} from {addr}")
        sender_ip, sender_port = addr
        peer_id, enet_packet = parse_turn_packet(data)
        if len(enet_packet) <= 0:
            self.register_peer(peer_id, sender_ip, sender_port)
        else:
            peer: YourTurnPeer = self._peer_map.get(peer_id, None)
            if peer is None:
                print(f"Invalid peer ID {peer_id}")
                return
            self.transport.write(data, peer.get_addr())

        # self.transport.write(data, addr)
        # if not self.is_relay_linked():
        #     # Attempt to register server
        #     if data != b"reg":
        #         return
        #     # TODO: Register received peer port
        #     self._server_ip, self._server_port = addr
        #     print(f"Server {self._server_ip}:{self._server_port} registered!")
        # else:
        #     if self.is_server(addr):
        #         # Data received from server - relay to client
        #         client_addr: tuple = self.get_client_address()
        #         if self.is_address_valid(client_addr):
        #             self.transport.write(data, client_addr)
        #     else:
        #         if not self.is_address_valid(self.get_client_address()):
        #             # Register client
        #             self._client_ip, self._client_port = addr
        #             print(f"Client {self._client_ip}:{self._client_port} registered!")
        #         if self.is_client(addr):
        #             # Data received from client - relay to server
        #             self.transport.write(data, self.get_server_address())
    
    def register_peer(self, id: int, ip: str, port: int) -> None:
        # TODO: Disallow reregistration if id lease is still valid
        reregistration: bool = id in self._peer_map
        print(f"Peer {id}[{ip}:{port}] {'re-' if reregistration else ''}registered")
        self._peer_map[id] = YourTurnPeer(ip, port)
    
    # def unregister_peer(peer_id: int) -> None:
    #     pass


if __name__ == '__main__':
    reactor.listenUDP(YOUR_TURN_PORT, YourTurnRelay())
    reactor.run()
