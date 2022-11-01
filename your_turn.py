from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

YOUR_TURN_PORT: int = 6942


class RelayServer(DatagramProtocol):
    def __init__(self) -> None:
        super().__init__()

        self._server_port = 6969
        self._client_port = 0

    def datagramReceived(self, data, addr) -> None:
        print(f"received {data!r} from {addr}")
        host, port = addr
        if self._client_port <= 0 and port != self._server_port:
            self._client_port = port

        if port == self._server_port:
            print(f"sending {data!r} to client, port {self._client_port}")
            self.transport.write(data, ('127.0.0.1', self._client_port))
        else:
            print(f"sending {data!r} to server, port {self._server_port}")
            self.transport.write(data, ('127.0.0.1', self._server_port))


if __name__ == '__main__':
    reactor.listenUDP(YOUR_TURN_PORT, RelayServer())
    reactor.run()
