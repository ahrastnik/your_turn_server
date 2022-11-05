import argparse
import struct
from time import perf_counter
from collections import deque
import statistics

from twisted.internet import reactor, task
from twisted.internet.protocol import DatagramProtocol

from your_turn import YOUR_TURN_PORT, make_turn_packet, parse_turn_packet
from your_turn_middleman import YourTurnMiddleman

YOUR_TURN_IP: str = "127.0.0.1"
MIDDLEMAN_IP: str = "127.0.0.1"
PING_DEFAULT_FREQUENCY: float = 100.0
PING_STAT_PUBLISH: float = 1.0


class ExampleClient(DatagramProtocol):
    def __init__(self,
                 client_id: int,
                 send_addr: tuple,
                 ping_frequency: float,
                 bypass: bool = False,
                 verbose: bool = False) -> None:
        super().__init__()

        self._id = client_id
        self._send_addr = send_addr
        self._ping_frequency = ping_frequency
        self._bypass = bypass
        self._verbose = verbose

        self._counter: int = 0
        self._ping_buffer = deque(maxlen=2048)

    def startProtocol(self):
        self.transport.connect(*self._send_addr)

        if self._bypass:
            # Register on Relay
            self.transport.write(make_turn_packet(self._id))

        if self._ping_frequency > 0:
            pinger = task.LoopingCall(self.ping_server)
            ping_delay = 1 / self._ping_frequency
            pinger.start(ping_delay, now=True)

            ping_statistics_publisher = task.LoopingCall(self.ping_publish_statistics)
            ping_statistics_publisher.start(PING_STAT_PUBLISH, now=False)

    def datagramReceived(self, data, addr):
        if self._verbose:
            print(f"received {data!r} from {addr}")

        # Parse packet when bypassing Middleman
        if self._bypass:
            parsed_packet = parse_turn_packet(data)
            if parsed_packet == ():
                print("Invalid packet received!")
                return
            peer_id, data = parsed_packet
            if len(data) <= 0:
                # Keep-alive packet, ignore
                return
            if self._id != peer_id:
                print(f"Received packet was not meant for this peer! {peer_id}")
                return

        # Calculate the time it took for the packet to reach server and back to client
        # TODO: Ping packets can get delivered unordered, so keep track of which packet is which
        counter: int
        departure_time: float
        counter, departure_time = struct.unpack(">Lf100x", data)
        ping_ms: float = (perf_counter() - departure_time) * 1000
        self._ping_buffer.append(ping_ms)

    def connectionRefused(self):
        print("Failed to reach Your TURN relay!")
        reactor.stop()

    def ping_server(self) -> None:
        payload = struct.pack(">Lf100x", self._counter, perf_counter())

        if self._bypass:
            payload = make_turn_packet(self._id, payload)

        self.transport.write(payload)
        self._counter += 1

    def ping_publish_statistics(self) -> None:
        if len(self._ping_buffer) < 2:
            return
        ping_mean = statistics.fmean(self._ping_buffer)
        ping_max = max(self._ping_buffer)
        ping_min = min(self._ping_buffer)
        ping_std = statistics.stdev(self._ping_buffer)
        print(f"Ping statistics [ms]: Mean:{ping_mean:.6f}\tMax:{ping_max:.6f}\tMin:{ping_min:.6f}\tSTD:{ping_std:.6f}")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        prog="Client Application example",
        description="Your TURN server - Client Application example"
    )
    arg_parser.add_argument("-i", "--id", type=int, default=69)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    arg_parser.add_argument("-r", "--relay-ip", default=YOUR_TURN_IP)
    arg_parser.add_argument("-p", "--relay-port", type=int, default=YOUR_TURN_PORT)
    arg_parser.add_argument("-f", "--frequency", type=float, default=PING_DEFAULT_FREQUENCY)
    arg_parser.add_argument("-b", "--bypass", action="store_true", help="Bypass Middleman")
    args = arg_parser.parse_args()

    send_address: tuple
    if not args.bypass:
        middleman = YourTurnMiddleman(args.relay_ip, args.relay_port, False, id=args.id, verbose=args.verbose)
        send_address = middleman.get_client_interface_addr()
    else:
        # Bypass Middleman and send directly to the Relay
        send_address = (args.relay_ip, args.relay_port)

    client_app = ExampleClient(args.id, send_address, args.frequency, bypass=args.bypass, verbose=args.verbose)
    reactor.listenUDP(0, client_app)
    reactor.run()
