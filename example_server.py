import argparse
import struct
from time import perf_counter

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT
from your_turn_middleman import YourTurnMiddleman

YOUR_TURN_IP: str = "127.0.0.1"
SERVER_PORT: int = 6942


class ExampleServer(DatagramProtocol):
    def __init__(self, verbose=False):
        super().__init__()

        self._verbose = verbose

    def startProtocol(self):
        pass

    def datagramReceived(self, data, addr):
        if self._verbose:
            print(f"received {data!r} from {addr}")
        # Echo data back
        self.transport.write(data, addr)
        # TODO: Calculate the time it took for the data to reach server
        # NOTE: perf_counter has an undefined start
        # counter, departure_time = struct.unpack(">Lf100x", data)
        # ping = perf_counter() - departure_time
        # print(f"TT [{counter}]:{ping}\ts")

    def connectionRefused(self):
        print("Failed to reach Your TURN relay!")
        reactor.stop()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        prog="Server Application example",
        description="Your TURN server - Server Application example"
    )
    arg_parser.add_argument("-p", "--port", type=int, default=SERVER_PORT)
    arg_parser.add_argument("-l", "--listen-port", type=int, default=YourTurnMiddleman.SERVER_DEFAULT_PORT)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    arg_parser.add_argument("-r", "--relay-ip", default=YOUR_TURN_IP)
    arg_parser.add_argument("-x", "--relay-port", type=int, default=YOUR_TURN_PORT)
    args = arg_parser.parse_args()

    # Run the Application first
    reactor.listenUDP(args.port, ExampleServer(verbose=args.verbose))
    middleman = YourTurnMiddleman(args.relay_ip, args.relay_port, True, server_port=args.listen_port, verbose=args.verbose)
    reactor.run()
