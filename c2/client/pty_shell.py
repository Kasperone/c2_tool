import os
import pty
import select
import sys
import threading


class PTYSession:
    """Persistent interactive PTY shell. Keeps a shell process alive across
    multiple commands so that state (cwd, env vars, shell builtins) persists."""

    def __init__(self):
        self.master_fd = None
        self.shell_pid = None

    def start(self):
        if self.master_fd is not None:
            return

        shell = os.environ.get("SHELL", "/bin/sh")
        pid, fd = pty.fork()

        if pid == 0:
            os.putenv("TERM", "xterm-256color")
            os.putenv("COLUMNS", "200")
            os.putenv("LINES", "50")
            os.execvp(shell, [shell])
        else:
            self.shell_pid = pid
            self.master_fd = fd

    def send_command(self, command: str, timeout: float = 5.0) -> str:
        if self.master_fd is None:
            self.start()

        marker = f"__C2_DONE_{os.getpid()}__"
        full_cmd = f"{command}\n echo {marker}\n"
        os.write(self.master_fd, full_cmd.encode())

        output = ""
        while True:
            ready, _, _ = select.select([self.master_fd], [], [], timeout)
            if not ready:
                break
            try:
                chunk = os.read(self.master_fd, 4096).decode(errors="replace")
            except OSError:
                break
            output += chunk
            if marker in output:
                break

        lines = output.split("\n")
        cleaned = []
        for line in lines:
            if marker in line:
                break
            cleaned.append(line)

        # Strip the first line (echoed command)
        if cleaned and cleaned[0].strip() == command.strip():
            cleaned = cleaned[1:]

        return "\n".join(cleaned).rstrip()

    def close(self):
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, b"exit\n")
            except OSError:
                pass
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.shell_pid is not None:
            try:
                import signal
                os.kill(self.shell_pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            self.shell_pid = None
