# C2 Tool — HTTP-Based C2 Framework

## Overview

Python HTTP-based Command and Control (C2) framework using Fernet (AES-128-CBC) encrypted communications. Traffic is disguised as normal HTTP requests to blend with web traffic.

**Authorized penetration testing and educational purposes only.**

## Architecture

```
c2_server.py  →  Threaded HTTP server (BaseHTTPRequestHandler)
                  Disguised as Apache/2.4.58 (CentOS)
                  Handles GET (commands + file downloads),
                  POST (output + CWD), PUT (file uploads)
c2_client.py  →  Polling loop, receives/decrypts commands,
                  executes locally, posts encrypted output back
encryption.py →  Fernet cipher initialization from KEY in settings
settings.py   →  All configuration: ports, keys, paths, proxies
```

## Communication Protocol

| Direction | Method | Path | Purpose |
|-----------|--------|------|---------|
| Client→Server | GET | `/book?isbn=<encrypted_client_id>` | Poll for command |
| Client→Server | GET | `/author?name=<encrypted_filepath>` | Request file download |
| Client→Server | PUT | `/reviews/<encrypted_filename>` | Upload file to server |
| Client→Server | POST | `/inventory` | Send command output |
| Client→Server | POST | `/title` | Send current working directory |

All payloads are Fernet-encrypted. The POST body uses `RESPONSE_KEY` as the form field name.

## Client Commands

| Command | Action |
|---------|--------|
| `client download <path>` | Transfer file from server to client |
| `client upload <path>` | Transfer file from client to server |
| `client zip <path>` | AES-encrypt a file on client (zip+LZMA) |
| `client unzip <path>` | Decrypt a zip on client |
| `client kill` | Terminate client process |
| `client sleep <secs>` | Pause client polling |
| `cd <dir>` | Change working directory on client |
| Any other text | Execute as shell command, return output |

## Session Management

- Server tracks clients in `pwned_dict` (key=session_id, value=`user@hostname@epoch`)
- `active_session` controls which client receives commands
- When a client disconnects or is killed, `get_new_session()` prompts for next session
- ThreadingMixIn allows concurrent client connections

## Setup & Run

```bash
# Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure settings.py: KEY, ZIP_PASSWORD, C2_SERVER, PORT
# Then:
python3 c2_server.py    # Start server
python3 c2_client.py    # Deploy on target
```

## Conventions

- Python 3.10+ (uses `int | str` union type syntax)
- No external frameworks — stdlib HTTP server + `requests` + `cryptography` + `pyzipper`
- Settings centralized in `settings.py` — both server and client import from it
- Server-side HTTP paths are designed to look like legitimate web traffic
- `log_request` overridden to suppress connection logging (stealth)

## Security Sensitivities

- **Never commit real keys** — `KEY` and `ZIP_PASSWORD` in `settings.py` are placeholders
- `packages.microsoft.gpg` is present in repo — appears to be a GPG key file, should probably be gitignored
- `incoming/` directory receives uploaded files — gitignore it
- `temp.py` is a scratch file — gitignore candidate

## Pitfalls

- Fernet key must be exactly 32 bytes after padding. The `pad_key()` function pads with `P` characters. If `KEY` in settings is >32 chars, initialization fails.
- The KEY is base64-encoded by `urlsafe_b64encode` after padding — Fernet expects a 32-byte URL-safe base64 key.
- Client identifies itself with `user@hostname@epoch` — the epoch timestamp means each client restart creates a new session entry.
- File uploads use `path.basename()` sanitization on the server to prevent path traversal.
- Azure/hosting environments may kill idle connections after ~4 minutes — `INPUT_TIMEOUT` + `KEEP_ALIVE_CMD` mitigate this.
- Proxy support requires matching the target network's proxy format in `settings.py`.

## File Inventory

| File | Purpose |
|------|---------|
| `c2_server.py` | C2 server — threaded HTTP handler with session management |
| `c2_client.py` | C2 implant — polling loop, command execution, file transfer |
| `encryption.py` | Fernet cipher setup from `KEY` |
| `settings.py` | All configurable values (shared by server + client) |
| `requirements.txt` | Python dependencies |
| `temp.py` | Scratch/testing file |
| `packages.microsoft.gpg` | Stray GPG key file (should be gitignored) |
