from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT

YOUR_TURN_IP: str = "127.0.0.1"
SERVER_PORT: int = 6969


class ExampleServer(DatagramProtocol):
    def startProtocol(self):
        self.transport.connect(YOUR_TURN_IP, YOUR_TURN_PORT)
        self.transport.write(b"reg")

    def datagramReceived(self, data, addr):
        print(f"received {data!r} from {addr}")
        # Echo back data
        self.transport.write(data)

    def connectionRefused(self):
        print("Failed to reach Your TURN relay!")
        reactor.stop()


if __name__ == "__main__":
    reactor.listenUDP(SERVER_PORT, ExampleServer())
    reactor.run()
