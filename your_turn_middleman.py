import argparse
from typing import Callable
from collections import deque

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.error import CannotListenError

from your_turn import (
    YOUR_TURN_PORT,
    parse_turn_packet,
    make_turn_packet,
)

YOUR_TURN_IP: str = "127.0.0.1"


class YourTurnMiddlemanInterface(DatagramProtocol):
    def __init__(self, id: int, recv_callback: Callable, send_port: int = 0, send_ip: str = "") -> None:
        self._id: int = id
        self._send_ip: str = send_ip
        self._send_port: int = send_port
        self._recv_callback: Callable = recv_callback

        self.__running: bool = False
        self.__send_buffer = deque()
    
    def is_running(self) -> bool:
        return self.__running

    def get_send_port(self) -> int:
        return self._send_port

    def set_send_port(self, send_port: int) -> None:
        self._send_port = send_port

    def is_send_port_set(self) -> bool:
        return self._send_port > 1024

    def get_send_addr(self) -> tuple:
        return (self._send_ip, self._send_port)

    def has_valid_send_addr(self) -> bool:
        return self._send_port > 1024 and self._send_ip != ""

    def startProtocol(self) -> None:
        self.__running = True
    	# Clear out send buffer
        # TODO: Try using self.transport.writeSequence(data) to write the entire buffer in one go
        while True:
            try:
                data: bytes = self.__send_buffer.popleft()
                self.transport.write(data, addr=self.get_send_addr())
            except IndexError:
                break
    
    def stopProtocol(self) -> None:
        self.__running = False

    def datagramReceived(self, data: bytes, addr: tuple) -> None:
        self._recv_callback(self._id, data, addr)
    
    def connectionRefused(self):
        # TODO: Implement handling of failed connections
        pass
    
    def send_data(self, data: bytes) -> None:
        if self.__running:
            self.transport.write(data, addr=self.get_send_addr())
        else:
            self.__send_buffer.append(data)


class YourTurnMiddlemanRelay(YourTurnMiddlemanInterface):
    def startProtocol(self) -> None:
        self.transport.connect(*self.get_send_addr())
        # Register interface on TURN server
        self.transport.write(make_turn_packet(self._id))
        super().startProtocol()


class YourTurnMiddlemanPeer(YourTurnMiddlemanInterface):
    def startProtocol(self) -> None:
        if self._send_port > 1024:
            # NOTE: The port can only be set once, so session has to be restarted if client changes
            # TODO: Optionally allow client changes
            self.transport.connect(self._send_ip, self._send_port)
        super().startProtocol()
    
    def set_send_port(self, send_port: int) -> None:
        super().set_send_port(send_port)
        if self.is_running() and send_port > 1024:
            self.transport.connect(self._send_ip, send_port)


class YourTurnMiddleman:
    # NOTE: ID of 1 is always assumed to be the server
    SERVER_ID: int = 1
    SERVER_DEFAULT_PORT: int = 6942
    PORT_RANGE_START: int = 6970
    # TODO: Implement peer limit
    # PEERS_MAX: int = 12

    def __init__(self,
                relay_ip: str,
                relay_port: int,
                is_server: bool,
                id: int = SERVER_ID,
                server_port: int = SERVER_DEFAULT_PORT,
                verbose: bool = False) -> None:
        
        self._relay_ip: str = relay_ip
        self._relay_port: int = relay_port
        self._is_server: bool = is_server
        self._server_port: int = server_port
        self._verbose: bool = verbose
        if is_server:
            if id != YourTurnMiddleman.SERVER_ID:
                raise ValueError("Server ID is always 1!")
        else:
            if id <= YourTurnMiddleman.SERVER_ID:
                raise ValueError("Client ID must be greater then 1 and in 32 bit range!")
        self._id: int = id
        self.relay = YourTurnMiddlemanRelay(
            self._id,
            self._received_from_relay,
            send_ip=relay_ip,
            send_port=relay_port
        )
        self._peers: dict = {}
        self._next_peer_port: int = YourTurnMiddleman.PORT_RANGE_START
        # Pre-register a peer on clients
        if not is_server:
            self.register_peer(id)

    def _received_from_relay(self, peer_id: int, turn_packet: bytes, addr: tuple) -> None:
        if self._verbose:
            print(f"received {turn_packet.hex()} from {addr}")
        
        parsed_turn_packet = parse_turn_packet(turn_packet)
        if parsed_turn_packet == ():
            print("Failed to parse TURN packet")
            return
        receiver_id: int
        payload: bytes
        receiver_id, payload = parsed_turn_packet
        
        # Received notification about a newly registered peer
        if len(payload) == 0:
            # Skip, this is a keep-alive echo message
            if receiver_id == self._id:
                return
            if self._is_server:
                # Attempt to Register peer on the first available port 
                while True:
                    try:
                        peer = self.register_peer(receiver_id)
                        if peer is None:
                            print("Failed to register peer!")
                            return
                    except CannotListenError as e:
                        print(e)
                    else:
                        break
            return
        
        peer: YourTurnMiddlemanPeer = self._peers.get(receiver_id, None)
        if peer is None:
            print("Invalid client peer ID received!")
            return
        
        # Forward received data to peer
        peer.send_data(payload)
    
    def _received_from_peer(self, peer_id: int, payload: bytes, addr: tuple) -> None:
        if self._verbose:
            print(f"received {payload.hex()} from {addr}")
        
        # Sending port has to be set in case of a client, as we don't know the clients port until it sends something
        ip, port = addr
        peer: YourTurnMiddlemanPeer = self._peers[peer_id]
        if not self._is_server and not peer.is_send_port_set():
            peer.set_send_port(port)
        
        receiver_id: int = peer_id if self._is_server else YourTurnMiddleman.SERVER_ID
        turn_packet: bytes = make_turn_packet(receiver_id, payload)
        # Forward received data to relay server
        self.relay.send_data(turn_packet)
    
    def register_peer(self, peer_id: int) -> YourTurnMiddlemanPeer:
        if peer_id <= 0 or peer_id in self._peers:
            return None
        
        peer = YourTurnMiddlemanPeer(peer_id, self._received_from_peer, send_ip="127.0.0.1")
        if self._is_server:
            peer.set_send_port(self._server_port)
        
        peer_port: int = self._next_peer_port
        self._next_peer_port += 1
        reactor.listenUDP(peer_port, peer)

        self._peers[peer_id] = peer
        
        print(f"Peer interface registered on port {peer_port}")
        return peer
    
    # def unregister_peer(self, peer_id: int) -> None:
    #     # TODO: Implement
    #     # TODO: Handle starting/stopping listeners
    #     pass
    
    def run(self):
        reactor.listenUDP(0, self.relay)
        reactor.run()


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        prog="Your TURN server middleman",
        description="Your TURN server peer side middleman"
    )
    arg_parser.add_argument("-s", "--server", action="store_true")
    arg_parser.add_argument("-i", "--id", type=int, default=1)
    arg_parser.add_argument("-l", "--listen-port", type=int, default=YourTurnMiddleman.SERVER_DEFAULT_PORT)
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    arg_parser.add_argument("-r", "--relay-ip", default=YOUR_TURN_IP)
    arg_parser.add_argument("-p", "--relay-port", type=int, default=YOUR_TURN_PORT)
    args = arg_parser.parse_args()

    middleman = YourTurnMiddleman(
        args.relay_ip,
        args.relay_port,
        args.server,
        id=args.id,
        server_port=args.listen_port,
        verbose=args.verbose
    )
    middleman.run()
