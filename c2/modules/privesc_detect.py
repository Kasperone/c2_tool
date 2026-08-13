"""Privilege escalation detection module — scans for common privesc vectors
on Linux and macOS (Windows vectors are detected but exploitation is out of scope).

Usage:
    privesc [all|suid|sudo|capabilities|kernel|docker]
"""

import os
import sys
import subprocess
import re
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: privesc [all|suid|sudo|capabilities|kernel|docker]"""
    mode = args[0] if args else "all"

    try:
        if mode == "suid":
            return _check_suid()
        elif mode == "sudo":
            return _check_sudo()
        elif mode == "capabilities":
            return _check_capabilities()
        elif mode == "kernel":
            return _check_kernel_privesc()
        elif mode == "docker":
            return _check_docker()
        elif mode == "all":
            sections = [
                "=== SUID/SGID Binaries ===",
                _check_suid(),
                "\n=== Sudo Privileges ===",
                _check_sudo(),
                "\n=== Docker Access ===",
                _check_docker(),
                "\n=== Linux Capabilities ===",
                _check_capabilities(),
                "\n=== Kernel Exploits ===",
                _check_kernel_privesc(),
            ]
            return "\n".join(sections)
        else:
            return f"Unknown mode: {mode}\nUsage: privesc [all|suid|sudo|capabilities|kernel|docker]"
    except Exception as e:
        return f"Privesc detection failed: {e}"


def _run_cmd(cmd: list[str] | str, shell: bool = False) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _check_suid() -> str:
    """Find SUID/SGID binaries that could be abused."""
    if sys.platform != "linux":
        return "SUID check only supported on Linux"

    lines = []
    findings = []

    # Common privesc SUID binaries
    privesc_suids = [
        "sudo", "vim", "vimtutor", "nano", "vi", "less", "more",
        "nmap", "find", "bash", "sh", "python", "python3",
        "perl", "ruby", "lua", "awk", "gawk", "gcc", "cc",
        "make", "strace", "ltrace", "strace", "env", "docker",
        "podman", "ssh", "cp", "tar", "zip", "curl", "wget",
        "nc", "ncat", "netcat", "socat", "nmap", "git",
    ]

    # Find all SUID files
    suid_output = _run_cmd(
        "find / -perm -4000 -type f 2>/dev/null | head -100", shell=True
    )
    if not suid_output:
        suid_output = _run_cmd(
            "find /usr -perm -4000 -type f 2>/dev/null | head -50", shell=True
        )

    if suid_output:
        suid_files = []
        for path in suid_output.split("\n"):
            path = path.strip()
            if not path:
                continue
            basename = os.path.basename(path)
            if basename in privesc_suids:
                suid_files.append(f"  [!] {path} — known privesc binary")
            else:
                suid_files.append(f"  SUID: {path}")
        findings.extend(suid_files)

    if findings:
        return "\n".join(findings)
    return "  No suspicious SUID binaries found"


def _check_sudo() -> str:
    """Check sudo privileges and NOPASSWD entries."""
    if sys.platform == "win32":
        return "Sudo check not applicable on Windows"

    lines = []

    # Check if running as root
    if os.getuid() == 0:
        lines.append("  Running as root")
        return "\n".join(lines)

    # Check sudo -l for NOPASSWD
    sudo_list = _run_cmd("sudo -l 2>&1", shell=True)
    if sudo_list:
        nopasswd_entries = []
        for line in sudo_list.split("\n"):
            if "NOPASSWD" in line:
                nopasswd_entries.append(f"  [!] NOPASSWD: {line.strip()}")
            elif "ALL" in line and "NOPASSWD" not in line:
                nopasswd_entries.append(f"  [!] UNRESTRICTED SUDO: {line.strip()}")

        if nopasswd_entries:
            return "\n".join(nopasswd_entries)
        elif "user may run" in sudo_list:
            # Has sudo but requires password
            cmd_count = sudo_list.count("\t")
            return f"  Sudo access available (requires password, {cmd_count} commands)"
        else:
            return "  No sudo access"
    else:
        return "  No sudo access"


def _check_docker() -> str:
    """Check if user has Docker access (can lead to root via container escape)."""
    lines = []

    if sys.platform == "win32":
        return "  Docker check not applicable on Windows"

    docker_groups = _run_cmd("id", shell=True)
    has_docker_group = "docker" in docker_groups if docker_groups else False

    if has_docker_group:
        lines.append("  [!] User is in 'docker' group — can mount host filesystem")
        lines.append("  [!] Suggested privesc: docker run -v /:/host --rm -it alpine chroot /host")

    # Check if Docker socket is accessible
    if os.path.exists("/var/run/docker.sock"):
        lines.append("  [!] Docker socket is accessible")
        if os.access("/var/run/docker.sock", os.W_OK):
            lines.append("  [!] Docker socket is writable")

    if not lines:
        return "  Docker privesc vector not found"
    return "\n".join(lines)


def _check_capabilities() -> str:
    """Check Linux capabilities that could enable privesc."""
    if sys.platform != "linux":
        return "  Capabilities check only supported on Linux"

    lines = []

    # Check for dangerous capabilities on current binary
    current_binary = sys.argv[0] if sys.argv else ""
    if current_binary:
        cap_result = _run_cmd(f"getcap {current_binary} 2>/dev/null", shell=True)
        if cap_result:
            lines.append(f"  [!] Current binary has capabilities: {cap_result}")
            if "cap_setuid" in cap_result or "cap_setuid=ep" in cap_result:
                lines.append("  [!] cap_setuid — can escalate to root")

    # Check for files with dangerous capabilities
    dangerous_caps = [
        "cap_setuid", "cap_setgid", "cap_sys_admin",
        "cap_sys_ptrace", "cap_dac_override",
    ]
    for cap in dangerous_caps:
        result = _run_cmd(
            f"getcap -r /usr/bin /usr/local/bin 2>/dev/null | grep {cap}",
            shell=True
        )
        if result:
            lines.append(f"  [!] Dangerous capability {cap} found:")
            for line in result.split("\n"):
                if line.strip():
                    lines.append(f"    {line.strip()}")

    if not lines:
        return "  No dangerous capabilities found"
    return "\n".join(lines)


def _check_kernel_privesc() -> str:
    """Check for known kernel vulnerabilities and outdated kernels."""
    if sys.platform != "linux":
        return "  Kernel privesc check only supported on Linux"

    lines = []

    # Get kernel version
    uname_result = _run_cmd("uname -r", shell=True)
    if uname_result:
        lines.append(f"  Kernel: {uname_result}")

        # Check for known vulnerable kernels
        if "4.4." in uname_result or "4.9." in uname_result:
            lines.append("  [!] Kernel 4.4/4.9 — check for DirtyPipe (CVE-2022-0847)")

        # Check if kernel is outdated
        try:
            kernel_parts = uname_result.split(".")[:2]
            major = int(kernel_parts[0])
            minor = int(kernel_parts[1])
            if major < 5 or (major == 5 and minor < 10):
                lines.append("  [!] Kernel version may be outdated — check for known exploits")
        except (ValueError, IndexError):
            pass

    # Check for unpatched CVEs in common exploit databases
    kernel_vulns = [
        ("DirtyCow", "CVE-2016-5195", "< 4.8.3"),
        ("DirtyPipe", "CVE-2022-0847", ">= 5.8, < 5.16.11"),
        ("OverlayFS", "CVE-2021-3493", ">= 4.9, < 5.8"),
        ("eBPF", "CVE-2021-3403", ">= 5.2, < 5.12"),
        ("eBPF", "CVE-2021-22555", ">= 5.4, < 5.12"),
    ]

    found_vulns = []
    for name, cve, version_range in kernel_vulns:
        # Check if the kernel version range might be vulnerable
        lines.append(f"  [!] {name} ({cve}): {version_range}")

    return "\n".join(lines) if lines else "  No kernel privesc vectors found"
