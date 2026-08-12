"""Local system enumeration — cross-platform recon module.
Gathers OS info, user/group data, network config, processes, and security products."""

import os
import sys
import platform
import subprocess
import socket
import getpass
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: enum_local [all|os|user|network|processes|security]"""
    mode = args[0] if args else "all"
    
    try:
        if mode == "os":
            return _enum_os()
        elif mode == "user":
            return _enum_user()
        elif mode == "network":
            return _enum_network()
        elif mode == "processes":
            return _enum_processes()
        elif mode == "security":
            return _enum_security()
        elif mode == "all":
            sections = [
                "=== OS Information ===",
                _enum_os(),
                "\n=== User Information ===",
                _enum_user(),
                "\n=== Network Information ===",
                _enum_network(),
                "\n=== Security Products ===",
                _enum_security(),
            ]
            return "\n".join(sections)
        else:
            return f"Unknown mode: {mode}\nUsage: enum_local [all|os|user|network|processes|security]"
    except Exception as e:
        return f"Enumeration failed: {e}"


def _run_cmd(cmd: list[str] | str, shell: bool = False) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _enum_os() -> str:
    """Enumerate OS information."""
    lines = []
    
    system = platform.system()
    
    if system == "Windows":
        lines.append(f"OS: {platform.platform()}")
        lines.append(f"Version: {platform.version()}")
        lines.append(f"Architecture: {platform.machine()}")
        lines.append(f"Processor: {platform.processor()}")
        lines.append(f"Hostname: {socket.gethostname()}")
        
        domain = _run_cmd("wmic computersystem get domain", shell=True)
        if domain and "Domain" in domain:
            domain_value = domain.split("\n")[-1].strip()
            lines.append(f"Domain: {domain_value}")
        
        uptime = _run_cmd("net statistics workstation", shell=True)
        if "since" in uptime:
            for line in uptime.split("\n"):
                if "since" in line:
                    lines.append(f"Uptime: {line.strip()}")
                    break
    
    else:
        lines.append(f"OS: {platform.system()} {platform.release()}")
        lines.append(f"Version: {platform.version()}")
        lines.append(f"Architecture: {platform.machine()}")
        lines.append(f"Hostname: {socket.gethostname()}")
        
        if system == "Linux":
            os_release = _run_cmd("cat /etc/os-release")
            if os_release:
                for line in os_release.split("\n"):
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip('"')
                        lines.append(f"Distribution: {pretty}")
                        break
            
            uptime = _run_cmd("uptime -p")
            if uptime:
                lines.append(f"Uptime: {uptime}")
        
        elif system == "Darwin":
            sw_vers = _run_cmd("sw_vers")
            if sw_vers:
                lines.append(f"macOS Version:\n{sw_vers}")
    
    return "\n".join(lines)


def _enum_user() -> str:
    """Enumerate current user information."""
    lines = []
    
    lines.append(f"Username: {getpass.getuser()}")
    lines.append(f"Home: {os.path.expanduser('~')}")
    
    if sys.platform == "win32":
        whoami = _run_cmd("whoami", shell=True)
        if whoami:
            lines.append(f"Full identity: {whoami}")
        
        groups = _run_cmd("whoami /groups", shell=True)
        if groups:
            lines.append(f"\nGroups:\n{groups}")
        
        privs = _run_cmd("whoami /priv", shell=True)
        if privs:
            lines.append(f"\nPrivileges:\n{privs}")
    
    else:
        uid = os.getuid()
        lines.append(f"UID: {uid}")
        
        id_output = _run_cmd("id")
        if id_output:
            lines.append(f"Identity: {id_output}")
        
        if uid == 0:
            lines.append("Privilege: ROOT")
        else:
            sudo_check = _run_cmd("sudo -n true 2>&1", shell=True)
            if not sudo_check or "password" not in sudo_check.lower():
                lines.append("Privilege: sudo (passwordless)")
    
    return "\n".join(lines)


def _enum_network() -> str:
    """Enumerate network configuration."""
    lines = []
    
    if sys.platform == "win32":
        ipconfig = _run_cmd("ipconfig /all", shell=True)
        if ipconfig:
            lines.append("Interfaces:")
            lines.append(ipconfig[:1500])
        
        route = _run_cmd("route print", shell=True)
        if route:
            lines.append(f"\nRouting Table:\n{route[:800]}")
        
        arp = _run_cmd("arp -a", shell=True)
        if arp:
            lines.append(f"\nARP Table:\n{arp[:800]}")
    
    else:
        if sys.platform == "linux":
            ip_addr = _run_cmd("ip addr", shell=True)
            if ip_addr:
                lines.append(f"Interfaces:\n{ip_addr[:1500]}")
            else:
                ifconfig = _run_cmd("ifconfig", shell=True)
                if ifconfig:
                    lines.append(f"Interfaces:\n{ifconfig[:1500]}")
            
            ip_route = _run_cmd("ip route", shell=True)
            if ip_route:
                lines.append(f"\nRouting Table:\n{ip_route}")
            else:
                route = _run_cmd("route -n", shell=True)
                if route:
                    lines.append(f"\nRouting Table:\n{route}")
            
            arp = _run_cmd("ip neigh", shell=True)
            if arp:
                lines.append(f"\nARP Table:\n{arp[:800]}")
            else:
                arp = _run_cmd("arp -a", shell=True)
                if arp:
                    lines.append(f"\nARP Table:\n{arp[:800]}")
        
        elif sys.platform == "darwin":
            ifconfig = _run_cmd("ifconfig", shell=True)
            if ifconfig:
                lines.append(f"Interfaces:\n{ifconfig[:1500]}")
            
            netstat = _run_cmd("netstat -rn", shell=True)
            if netstat:
                lines.append(f"\nRouting Table:\n{netstat[:800]}")
            
            arp = _run_cmd("arp -a", shell=True)
            if arp:
                lines.append(f"\nARP Table:\n{arp[:800]}")
    
    return "\n".join(lines)


def _enum_processes() -> str:
    """Enumerate running processes."""
    if sys.platform == "win32":
        return _run_cmd("tasklist /v", shell=True)[:2000]
    else:
        ps = _run_cmd("ps aux", shell=True)
        if ps:
            return ps[:2000]
        return "Process enumeration failed"


def _enum_security() -> str:
    """Enumerate security products (AV, EDR, firewall)."""
    lines = []
    
    if sys.platform == "win32":
        wmic_av = _run_cmd("wmic /namespace:\\\\root\\SecurityCenter2 path AntiVirusProduct get displayName,productState", shell=True)
        if wmic_av and "displayName" in wmic_av:
            lines.append("Antivirus Products:")
            lines.append(wmic_av)
        else:
            lines.append("Antivirus: None detected via WMI")
        
        firewall = _run_cmd("netsh advfirewall show allprofiles state", shell=True)
        if firewall:
            lines.append(f"\nFirewall Status:\n{firewall}")
        
        defender = _run_cmd("Get-MpComputerStatus", shell=True)
        if defender and "AMRunningMode" in defender:
            lines.append(f"\nWindows Defender:\n{defender[:500]}")
    
    else:
        lines.append("Security Products (Linux/macOS):")
        
        if sys.platform == "linux":
            av_checks = [
                ("ClamAV", "clamscan --version"),
                ("Sophos", "sav-protect --version"),
                ("ESET", "esets_scan --version"),
                ("Kaspersky", "kav4ws-kavscanner --version"),
            ]
            
            found_av = []
            for name, cmd in av_checks:
                if _run_cmd(cmd, shell=True):
                    found_av.append(name)
            
            if found_av:
                lines.append(f"  Antivirus: {', '.join(found_av)}")
            else:
                lines.append("  Antivirus: None detected")
            
            iptables = _run_cmd("iptables -L -n 2>/dev/null", shell=True)
            if iptables and "Chain" in iptables:
                lines.append(f"\n  Firewall (iptables): Active\n{iptables[:500]}")
            else:
                nftables = _run_cmd("nft list ruleset 2>/dev/null", shell=True)
                if nftables:
                    lines.append(f"\n  Firewall (nftables): Active\n{nftables[:500]}")
                else:
                    lines.append("\n  Firewall: None detected")
            
            selinux = _run_cmd("getenforce 2>/dev/null", shell=True)
            if selinux:
                lines.append(f"\n  SELinux: {selinux}")
            
            apparmor = _run_cmd("aa-status 2>/dev/null", shell=True)
            if apparmor:
                lines.append(f"\n  AppArmor: Active\n{apparmor[:300]}")
        
        elif sys.platform == "darwin":
            xprotect = _run_cmd("system_profiler SPInstallDataType | grep -A2 XProtect", shell=True)
            if xprotect:
                lines.append(f"  XProtect:\n{xprotect}")
            
            firewall = _run_cmd("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate", shell=True)
            if firewall:
                lines.append(f"\n  Firewall: {firewall}")
            
            gatekeeper = _run_cmd("spctl --status")
            if gatekeeper:
                lines.append(f"\n  Gatekeeper: {gatekeeper}")
    
    return "\n".join(lines)
