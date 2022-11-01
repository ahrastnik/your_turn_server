from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6942


class YourTurnRelay(DatagramProtocol):
    def __init__(self) -> None:
        super().__init__()

        self._server_ip: str = ""
        self._server_port: int = 0
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
