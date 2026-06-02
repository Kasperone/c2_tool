# C2 Tool — Technical Reference (AGENTS.md)

## Overview

Modular Python C2 framework with YAML config, plugin system, multiple transports, and
post-exploitation modules. Built from a flat-file HTTP C2 into a package-structured system.

**Authorized penetration testing and educational purposes only.**

## Architecture

```
c2_tool/
├── config/
│   ├── default.yaml          # Main config (ports, keys, beacon, logging, mTLS, profile)
│   ├── config.py             # YAML loader + Config class with attribute access
│   ├── profile_handler.py    # Malleable profile: rotated headers, URI building
│   └── profiles/             # Per-profile YAML (jquery_cdn, amazon_cdn, ...)
├── c2/
│   ├── client/
│   │   ├── client.py         # Main loop: beacon, command dispatch, module calls
│   │   ├── beacon.py         # jittered_sleep()
│   │   ├── commands.py       # run_shell_command(), change_directory()
│   │   └── pty_shell.py      # PTYSession: persistent shell via pty.fork()
│   ├── server/
│   │   ├── server.py         # run_server(): instantiates handler, session mgr, logging
│   │   ├── handler.py        # C2Handler (BaseHTTPRequestHandler) with profile-aware routing
│   │   └── sessions.py       # SessionManager: centralized state, command queue
│   ├── transport/
│   │   ├── mtls.py           # CA/cert generation, SSL contexts, pinning
│   │   ├── socks_proxy.py    # SOCKS5 proxy (SOCKSProxy + Tunnel)
│   │   └── websocket_client.py  # WebSocketClient + WebSocketServer (async)
│   ├── modules/
│   │   ├── loader.py         # ModuleLoader: dynamic import + execute_from_source()
│   │   ├── portscan.py       # TCP connect scan, port ranges, service detection
│   │   ├── credharvest.py    # Chrome/Edge creds, SSH keys, WiFi, shell history
│   │   ├── screenshot.py     # Cross-platform capture (GDI, screencapture, scrot)
│   │   ├── keylogger.py      # Windows GAK / Linux evdev / macOS pynput
│   │   ├── rportfwd.py       # ReverseForward + TunnelPair (bidirectional relay)
│   │   ├── persistence.py    # cron, systemd, registry Run, scheduled tasks
│   │   ├── p2p_pivot.py      # PivotNode: TCP chaining between implants
│   │   ├── dns_tunnel.py     # DNSTunnelServer/Client: TXT record tunnel
│   │   └── multi_op.py       # AsyncC2Server (aiohttp) + OperatorAuth (SQLite)
│   ├── crypto/
│   │   └── encryption.py     # create_cipher() — Fernet factory
│   └── logging/
│       └── activity_log.py   # ActivityLog: SQLite sessions/commands/events
├── payloads/
│   └── generator.py          # PyInstaller wrapper + PowerShell stager
├── run_server.py             # Server entry point
├── run_client.py             # Client entry point
├── generate_payload.py       # Payload generation CLI
├── requirements.txt
│
├── c2_server.py              # (legacy) Original monolithic server
├── c2_client.py              # (legacy) Original monolithic client
├── encryption.py             # (legacy) Original encryption module
└── settings.py               # (legacy) Original hardcoded settings
```

## Communication Protocol

| Direction | Method | Path (default) | Purpose |
|-----------|--------|---------------|---------|
| Client→Server | GET | `/book?isbn=<client_id>` | Poll for command |
| Client→Server | GET | `/author?name=<filepath>` | Download file |
| Client→Server | PUT | `/reviews/<filename>` | Upload file |
| Client→Server | POST | `/inventory` | Command output |
| Client→Server | POST | `/title` | CWD update |

Paths are overridden by malleable profiles (`config/profiles/*.yaml`).
With a profile active, URIs look like `/ajax/libs/jquery/3.7.1/jquery.min.js?v=abc123`.

## Command Protocol

Every client-side command is prefixed with `client`:

| Command | Action |
|---------|--------|
| `client download <path>` | Transfer file from server to client |
| `client upload <path>` | Transfer file from client to server |
| `client zip <path>` | AES-encrypt file (zip+LZMA) |
| `client unzip <path>` | Decrypt zip |
| `client kill` | Terminate implant |
| `client sleep <secs>` | Pause polling |
| `client pty start` | Start persistent PTY shell |
| `client pty close` | Close PTY |
| `client pty <cmd>` | Send command to PTY |
| `client persist cron\|systemd\|registry\|task` | Install persistence |
| `client socks start [port]` | Start SOCKS5 proxy on implant |
| `client socks stop` | Stop SOCKS5 proxy |
| `client scan <host> [ports] [timeout]` | TCP port scan |
| `client screenshot [path]` | Capture screen |
| `client keylog start\|stop\|dump\|status` | Keylogger |
| `client credharvest all\|ssh\|chrome\|history\|wifi` | Credential harvesting |
| `client rportfwd create <id> <lport> <rhost> <rport>` | Reverse port forward |
| `client rportfwd remove <id>` | Close tunnel |
| `client rportfwd list` | Show active tunnels |
| `client p2p create_pivot <name> <host> <port>` | P2P pivot node |
| `client p2p create_leaf <name> <pivot_host> <port>` | P2P leaf node |
| `client dns server start <domain> <key>` | DNS tunnel server |
| `client dns client query <domain> <key> <sid> <data>` | DNS tunnel client |
| `client multiop server start [host] [port]` | Async multi-operator server |
| `client multiop operator create <username>` | Create operator token |
| `client module <name> [args...]` | Execute arbitrary module |
| `cd <dir>` | Change directory (no prefix) |
| `<any other text>` | Shell command (no prefix) |

Server-side commands (operator console):
- `sessions` — list connected sessions
- `use <id>` — switch active session
- Anything else is queued for the active session's next beacon

## Session Model

`SessionManager` (c2/server/sessions.py) holds all state:
- `sessions` dict: {session_id: client_string}
- `pending_commands` dict: {session_id: command} — set by operator, dequeued on beacon
- `active_session_id`, `active_cwd`, `client_account`, `client_hostname`

The server no longer blocks on `input()` during an HTTP request. Commands are
queued asynchronously and delivered when the implant next beacons in.

## Config System

`config/default.yaml` is the runtime config. Key sections:

```yaml
network:
  port: 80
  bind_address: ""
  c2_server: "localhost"
beacon:
  sleep_seconds: 60
  jitter_percent: 20
logging:
  enabled: true
  database: "c2_activity.db"
mtls: { enabled: false, ca_cert: null, ... }
profile: null              # or "jquery_cdn" / "amazon_cdn"
domain_fronting: { enabled: false, cdn_host: null, ... }
payload: { output_format: "exe", ... }
```

Load at runtime: `from config import load_config; cfg = load_config("config.yaml")`
Access via attribute: `cfg.beacon.sleep_seconds`, `cfg.network.port`, etc.

## Malleable Profiles

Profiles in `config/profiles/*.yaml` define:
- `uri_pattern` — base path for each request type
- `uri_random_suffix` — append `?v=random6` per request
- Header dicts with `_rotation` lists (User-Agent, Accept-Language, Referer)
- `post_key` for POST request form fields

Activate via `profile: jquery_cdn` in default.yaml or `C2_PROFILE` env var.

## Plugin System

Modules live in `c2/modules/`. Each must expose:

```python
def run(args: list[str]) -> str:
    ...
```

Two loading paths:
1. **ModuleLoader.load_module(name)** — imports from `c2/modules/<name>.py`
2. **ModuleLoader.execute_from_source(source)** — runs Python source sent by server

Built-in modules: portscan, credharvest, screenshot, keylogger, rportfwd, p2p_pivot, dns_tunnel, multi_op, persistence, loader

## Activity Logging

`c2/logging/activity_log.py` — SQLite backend with three tables:

- `sessions` — session_id, client_name, hostname, account, first_seen, last_seen
- `commands` — session_id, timestamp, command, output, status
- `events` — session_id, timestamp, event_type, detail

Thread-safe via `threading.local()` connection per thread.

## Conventions

- Python 3.10+ (uses `int | None` union syntax, `match` statements where applicable)
- Type annotations throughout; Pyright-friendly
- YAML for config (never Python constants)
- No external frameworks for server (stdlib http.server + threading)
- aiohttp used only for multi-operator async server module
- Each module is self-contained with a `run()` entry point

## Pitfalls

- Fernet key must be ≤32 bytes before padding. `pad_key()` fills with `P`.
- Fernet key is base64-encoded internally after padding — `urlsafe_b64encode(pad_key(KEY).encode())`.
- Client identifies as `user@hostname@epoch` — epoch means each restart creates a new session.
- File uploads use `path.basename()` sanitization — prevents path traversal from implant.
- `INPUT_TIMEOUT` + `KEEP_ALIVE_CMD` mitigate Azure/hosting idle-connection kills (~4min).
- SOCKS proxy requires the implant to have network access to the target segment.
- DNS tunnel requires DNS server to delegate the tunnel domain to the implant host.
- P2P pivot requires the pivot implant to have bidirectional TCP access to both team server and leaf implants.
- Persistence modules (systemd, registry) typically require elevated privileges.
- mTLS cert generation requires `openssl` binary on PATH.
- WebSocket transport requires `websockets` package (added to requirements.txt).
- Multi-operator async server requires `aiohttp` (added to requirements.txt).
- Keylogger on Linux may need root or `input` group access to `/dev/input/event*`.
- Keylogger on macOS requires Accessibility permissions for pynput.
- Chrome credential decryption on Windows requires DPAPI (not implemented — encrypted blob is returned).

## Security Sensitivities

- **Never commit real keys** — KEY and ZIP_PASSWORD are placeholders
- `packages.microsoft.gpg` — stray GPG key file, should be gitignored
- `incoming/` directory receives uploaded files — gitignore it
- `temp.py` — scratch file, gitignore candidate
- `c2_activity.db` — contains all captured outputs — gitignore it
- `operators.db` — contains operator tokens — gitignore it
- Certificate files (`*.crt`, `*.key`) — gitignore all
