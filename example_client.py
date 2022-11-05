import argparse
import struct
from time import perf_counter

from twisted.internet import reactor, task
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT
from your_turn_middleman import YourTurnMiddleman

YOUR_TURN_IP: str = "127.0.0.1"
MIDDLEMAN_IP: str = "127.0.0.1"
PING_FREQUENCY: float = 1.0


class ExampleClient(DatagramProtocol):
    def __init__(self, ping_frequency: float, middleman_addr: tuple = (), verbose: bool = False) -> None:
        super().__init__()

        self._ping_frequency = ping_frequency
        self._middleman_addr = middleman_addr
        self._verbose = verbose

        self._counter = 0

    def startProtocol(self):
        if self._middleman_addr != ():
            self.transport.connect(*self._middleman_addr)
        # Send some data every second
        if self._ping_frequency > 0:
            loop = task.LoopingCall(self.ping_server)
            ping_delay = 1 / self._ping_frequency
            loop.start(ping_delay, now=True)

    def datagramReceived(self, data, addr):
        if self._verbose:
            print(f"received {data!r} from {addr}")
        # Calculate the time it took for the packet to reach server and back to client
        # TODO: Ping packets can get delivered unordered, so keep track of which packet is which
        counter: int
        departure_time: float
        counter, departure_time = struct.unpack(">Lf100x", data)
        ping_ms: float = (perf_counter() - departure_time) * 1000
        print(f"RTT [{counter}]:{ping_ms}\tms")

    def connectionRefused(self):
        print("Failed to reach Your TURN relay!")
        reactor.stop()

    def ping_server(self) -> None:
        packet = struct.pack(">Lf100x", self._counter, perf_counter())
        self.transport.write(packet)
        self._counter += 1


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        prog="Client Application example",
        description="Your TURN server - Client Application example"
    )
    arg_parser.add_argument("-i", "--id", type=int, default=69)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    arg_parser.add_argument("-r", "--relay-ip", default=YOUR_TURN_IP)
    arg_parser.add_argument("-p", "--relay-port", type=int, default=YOUR_TURN_PORT)
    arg_parser.add_argument("-f", "--frequency", type=float, default=PING_FREQUENCY)
    args = arg_parser.parse_args()

    # Run the Middleman first
    middleman = YourTurnMiddleman(args.relay_ip, args.relay_port, False, id=args.id, verbose=args.verbose)
    middleman_address = middleman.get_client_interface_addr()
    client_app = ExampleClient(args.frequency, middleman_addr=middleman_address, verbose=args.verbose)
    reactor.listenUDP(0, client_app)
    reactor.run()
