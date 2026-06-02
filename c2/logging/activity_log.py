import sqlite3
import os
import threading
from datetime import datetime, timezone


class ActivityLog:
    def __init__(self, db_path: str = "c2_activity.db", enabled: bool = True):
        self.enabled = enabled
        self.db_path = db_path
        self._local = threading.local()
        if self.enabled:
            self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER UNIQUE NOT NULL,
                client_name TEXT NOT NULL,
                hostname TEXT,
                account TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                command TEXT NOT NULL,
                output TEXT,
                status TEXT DEFAULT 'success',
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT
            );
        """)
        conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_session(self, session_id: int, client_name: str, hostname: str = "", account: str = ""):
        if not self.enabled:
            return
        conn = self._get_conn()
        now = self._now()
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, client_name, hostname, account, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT first_seen FROM sessions WHERE session_id=?), ?), ?)",
            (session_id, client_name, hostname, account, session_id, now, now),
        )
        conn.execute(
            "INSERT INTO events (session_id, timestamp, event_type, detail) VALUES (?, ?, 'session_new', ?)",
            (session_id, now, client_name),
        )
        conn.commit()

    def log_command(self, session_id: int, command: str, output: str = "", status: str = "success"):
        if not self.enabled:
            return
        conn = self._get_conn()
        now = self._now()
        conn.execute(
            "INSERT INTO commands (session_id, timestamp, command, output, status) VALUES (?, ?, ?, ?, ?)",
            (session_id, now, command, output, status),
        )
        conn.commit()

    def log_event(self, event_type: str, detail: str = "", session_id: int = None):
        if not self.enabled:
            return
        conn = self._get_conn()
        now = self._now()
        conn.execute(
            "INSERT INTO events (session_id, timestamp, event_type, detail) VALUES (?, ?, ?, ?)",
            (session_id, now, event_type, detail),
        )
        conn.commit()

    def get_session_history(self, session_id: int = None, limit: int = 100):
        if not self.enabled:
            return []
        conn = self._get_conn()
        if session_id is not None:
            rows = conn.execute(
                "SELECT * FROM commands WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM commands ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_events(self, limit: int = 100):
        if not self.enabled:
            return []
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
