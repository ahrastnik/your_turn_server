import struct

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6942

# Packet structure: UDP<TURN<prefix: uint16, sender id: uint32, ENet packet>>
TURN_MSG_PREFIX: int = 0xAA


def parse_turn_packet(self, turn_packet: bytes) -> bytes:
    # TODO: Verify sender id is valid
    if len(turn_packet) <= 6:
        return ()
    
    preamble = struct.unpack(">HL", turn_packet[:6])
    prefix, sender_id = preamble
    if prefix != TURN_MSG_PREFIX:
        return ()
    
    return (sender_id, turn_packet[6:])


def make_turn_packet(self, id: int, enet_packet: bytes) -> bytes:
    preamble: bytes = struct.pack(">HL", TURN_MSG_PREFIX, id)
    return preamble + enet_packet


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
        self.transport.write(data, addr)
        if not self.is_relay_linked():
            # Attempt to register server
            if data != b"reg":
                return
            
            self._server_ip, self._server_port = addr
            print(f"Server {self._server_ip}:{self._server_port} registered!")
        else:
            if self.is_server(addr):
                # Data received from server - relay to client
                client_addr: tuple = self.get_client_address()
                if self.is_address_valid(client_addr):
                    self.transport.write(data, client_addr)
            else:
                if not self.is_address_valid(self.get_client_address()):
                    # Register client
                    self._client_ip, self._client_port = addr
                    print(f"Client {self._client_ip}:{self._client_port} registered!")
                if self.is_client(addr):
                    # Data received from client - relay to server
                    self.transport.write(data, self.get_server_address())
    
    # def register_server() -> None:
    #     pass
    
    # def unregister_server() -> None:
    #     pass


if __name__ == '__main__':
    reactor.listenUDP(YOUR_TURN_PORT, YourTurnRelay())
    reactor.run()
