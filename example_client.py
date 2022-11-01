from twisted.internet import reactor, task
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT

YOUR_TURN_IP: str = "127.0.0.1"


class ExampleClient(DatagramProtocol):
    def __init__(self) -> None:
        super().__init__()

        self._counter = 0

    def startProtocol(self):
        self.transport.connect(YOUR_TURN_IP, YOUR_TURN_PORT)
        # Send some data every second
        loop = task.LoopingCall(self.send_data)
        loop.start(1.0, now=True)

    def datagramReceived(self, data, addr):
        print(f"received {data!r} from {addr}")

    def connectionRefused(self):
        print("Failed to reach Your TURN relay!")
        reactor.stop()

    def send_data(self) -> None:
        self.transport.write(f"hello {self._counter}".encode())
        self._counter += 1


if __name__ == "__main__":
    # 0 means any port, we don't care in this case
    reactor.listenUDP(0, ExampleClient())
    reactor.run()
