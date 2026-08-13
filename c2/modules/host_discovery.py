"""Host discovery module — network reconnaissance to find live hosts on local
subnets via ARP ping sweeps and ICMP scans.

Usage:
    host_discovery [all|arp|icmp|subnets]
"""

import os
import sys
import subprocess
import socket
import struct
import time
import concurrent.futures
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: host_discovery [all|arp|icmp|subnets]"""
    mode = args[0] if args else "all"

    try:
        if mode == "arp":
            return _arp_discovery()
        elif mode == "icmp":
            return _icmp_discovery()
        elif mode == "subnets":
            return _enumerate_subnets()
        elif mode == "all":
            results = [
                "=== Subnet Information ===",
                _enumerate_subnets(),
                "\n=== ARP Discovery ===",
                _arp_discovery(),
                "\n=== ICMP Ping Sweep ===",
                _icmp_discovery(),
            ]
            return "\n".join(results)
        else:
            return f"Unknown mode: {mode}\nUsage: host_discovery [all|arp|icmp|subnets]"
    except Exception as e:
        return f"Host discovery failed: {e}"


def _run_cmd(cmd: list[str] | str, shell: bool = False) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _enumerate_subnets() -> str:
    """Enumerate local subnets from network configuration."""
    lines = []

    if sys.platform == "win32":
        ipconfig = _run_cmd("ipconfig /all", shell=True)
        if ipconfig:
            for line in ipconfig.split("\n"):
                if "IP Address" in line or "Subnet Mask" in line:
                    lines.append(f"  {line.strip()}")
    else:
        if sys.platform == "linux":
            ip_addr = _run_cmd("ip addr", shell=True)
            if ip_addr:
                for line in ip_addr.split("\n"):
                    line = line.strip()
                    if line.startswith("inet "):
                        lines.append(f"  {line}")
        elif sys.platform == "darwin":
            ifconfig = _run_cmd("ifconfig", shell=True)
            if ifconfig:
                for line in ifconfig.split("\n"):
                    line = line.strip()
                    if "inet " in line and "127.0.0.1" not in line:
                        lines.append(f"  {line}")

    return "\n".join(lines) if lines else "No local interfaces found"


def _arp_discovery() -> str:
    """Perform ARP table analysis and optional ARP scan."""
    lines = []

    if sys.platform == "win32":
        arp = _run_cmd("arp -a", shell=True)
        if arp:
            lines.append(f"  ARP Table:\n{arp[:2000]}")
    else:
        if sys.platform == "linux":
            arp = _run_cmd("ip neigh", shell=True)
            if arp:
                lines.append(f"  Neighbors:\n{arp[:2000]}")
            else:
                arp = _run_cmd("arp -a", shell=True)
                if arp:
                    lines.append(f"  ARP Table:\n{arp[:2000]}")
        elif sys.platform == "darwin":
            arp = _run_cmd("arp -a", shell=True)
            if arp:
                lines.append(f"  ARP Table:\n{arp[:2000]}")

    # Try ARP scan if running as root
    if os.getuid() == 0 or sys.platform == "win32":
        lines.append("  Performing ARP scan...")
        lines.extend(_arp_scan())

    return "\n".join(lines) if lines else "ARP discovery failed"


def _arp_scan() -> list[str]:
    """Scan local subnet using ARP requests to discover live hosts."""
    lines = []
    discovered = []

    # Get local IP and subnet
    local_ip = _get_local_ip()
    if not local_ip:
        lines.append("  No local IP found for scanning")
        return lines

    # Extract subnet (assuming /24)
    subnet_prefix = ".".join(local_ip.split(".")[:3])

    lines.append(f"  Scanning {subnet_prefix}.0/24 via ARP...")

    for i in range(1, 255):
        ip = f"{subnet_prefix}.{i}"
        if sys.platform == "linux":
            result = subprocess.run(
                ["arping", "-c", "1", "-W", "1", ip],
                capture_output=True, text=True, timeout=2
            )
            if "Unicast reply" in result.stdout:
                discovered.append(ip)
        elif sys.platform == "win32":
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", ip],
                capture_output=True, text=True, timeout=2
            )
            if "TTL=" in result.stdout or "Reply" in result.stdout:
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    hostname = ip
                discovered.append(f"{ip} ({hostname})")

    if discovered:
        lines.append(f"  Live hosts found: {len(discovered)}")
        for host in discovered:
            lines.append(f"    - {host}")
    else:
        lines.append("  No additional hosts discovered via ARP")

    return lines


def _icmp_discovery() -> str:
    """Perform ICMP ping sweep of local subnet."""
    lines = []

    local_ip = _get_local_ip()
    if not local_ip:
        return "No local IP found for ICMP sweep"

    subnet_prefix = ".".join(local_ip.split(".")[:3])

    lines.append(f"Ping sweep of {subnet_prefix}.0/24 (threaded)...")

    def _ping_host(ip: str) -> str | None:
        """Ping a single host and return it if alive."""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    hostname = ip
                return f"{ip} ({hostname})"
        except Exception:
            pass
        return None

    hosts = []
    ips = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
        futures = list(pool.map(_ping_host, ips))
    hosts = [r for r in futures if r is not None]

    if hosts:
        lines.append(f"  Live hosts: {len(hosts)}")
        lines.append("  " + "\n  ".join(sorted(hosts)[:50]))
    else:
        lines.append("  No live hosts found")

    return "\n".join(lines)


def _get_local_ip() -> Optional[str]:
    """Get the primary local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None
