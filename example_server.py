from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT

YOUR_TURN_IP: str = "127.0.0.1"
SERVER_PORT: int = 6969


class ExampleServer(DatagramProtocol):
    def __init__(self, turn_ip: str, turn_port: int) -> None:
        super().__init__()
        ExampleServer.TURN_IP: str = turn_ip
        ExampleServer.TURN_PORT: int = turn_port
    
    def startProtocol(self):
        self.transport.connect(ExampleServer.TURN_IP, ExampleServer.TURN_PORT)
        self.transport.write(b"reg")

    def datagramReceived(self, data, addr):
        print(f"received {data!r} from {addr}")
        # Echo back data
        self.transport.write(data)

    def connectionRefused(self):
        print("Failed to reach your TURN relay!")


if __name__ == "__main__":
    reactor.listenUDP(SERVER_PORT, ExampleServer(YOUR_TURN_IP, YOUR_TURN_PORT))
    reactor.run()
