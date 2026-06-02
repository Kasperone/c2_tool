# C2 Tool — Feature Gap Analysis & Implementation Roadmap

> Generated from the C2 Frameworks Capability Report (2026).
> This file maps what our c2_tool currently implements vs. what modern C2 frameworks offer.

## Implementation Status: Phases 1–4 COMPLETE

All HIGH and MEDIUM priority items in the phased plan below have been implemented.
Remaining items are LOW priority (SaaS channels, kill date, working-hours, BOF) or
require a compiled implant rewrite (in-memory evasion category C).

## Current Implementation Status

### What we HAVE:
- **HTTP/HTTPS transport** — single channel, GET for commands, POST for responses, PUT for file uploads
- **Fernet encryption** (AES-128-CBC) on all comms
- **Shell command execution** — arbitrary commands via subprocess
- **File operations** — upload (server→client), download (client→server)
- **ZIP encrypt/decrypt** on client side (AES + LZMA)
- **cd** — change working directory
- **client kill / client sleep** — session lifecycle
- **Multi-session** — basic session switching via dictionary
- **Apache server impersonation** — Server-Version header spoofing
- **Custom User-Agent** — browser-like header
- **Static proxy support** — hardcoded proxy dict in settings
- **Cross-platform client** — Windows/Linux/macOS detection

---

## MISSING FEATURES (by category)

### A. Communication & Transport

| Feature | Priority | Description |
|---------|----------|-------------|
| Beaconing with jitter | HIGH | Replace tight polling loop with configurable sleep + random jitter (e.g. sleep 60s ± 20%). This is the baseline for blending into normal traffic. |
| mTLS / mutual TLS | HIGH | Per-implant certificates, certificate pinning. Currently using plain HTTP with Fernet on top — vulnerable to MITM if key is compromised. |
| DNS tunneling | MEDIUM | TXT/A/AAAA record tunneling as alternative C2 channel. Bypasses HTTP-only egress filters. |
| WebSocket transport | MEDIUM | Persistent bidirectional channel. Lower latency than HTTP polling, looks like normal web traffic. |
| P2P / pivot links | MEDIUM | Implants chain via SMB named pipes or TCP so only one host egresses. Critical for segmented networks. |
| Third-party channels | LOW | C2 over Slack, Telegram, Discord, GitHub Gists, cloud APIs. Bypasses network monitoring by using trusted SaaS traffic. |
| Kill date | LOW | Implant self-terminates after a configured date. Operational hygiene. |
| Working-hours restriction | LOW | Implant only beacons during business hours to blend with normal user activity. |
| Domain fronting / redirectors | MEDIUM | Route callbacks through CDNs (CloudFront, Azure CDN) so real team server IP is never exposed. |

### B. Traffic Shaping (Malleable C2 Profiles)

| Feature | Priority | Description |
|---------|----------|-------------|
| Malleable C2 profiles | HIGH | Config-driven traffic shaping: custom URIs, headers, cookies, body shapes. Makes each deployment's traffic look like a different legitimate app (e.g., Amazon, jQuery CDN). |
| Configurable URI patterns | HIGH | Randomized URI paths per callback instead of static `/book?isbn=`. Defeats URI-based detection. |
| Header randomization | MEDIUM | Rotate User-Agent, Accept-Language, Referer per request. Current static header is fingerprintable. |
| Data hiding in cookies/headers | MEDIUM | Hide C2 data in Cookie values or custom headers instead of URL params and POST bodies. |
| Response body shaping | MEDIUM | Server responses mimic real pages (HTML, JSON) with data steganographically embedded. |

### C. In-Memory Evasion

| Feature | Priority | Description |
|---------|----------|-------------|
| Sleep obfuscation | HIGH | Encrypt implant memory while idle (Ekko/Foliage/Zilean techniques). Defeats memory scanning between callbacks. |
| Stack spoofing | MEDIUM | Fake call stack during sleep so implant doesn't look like injected code. |
| Direct/indirect syscalls | MEDIUM | Bypass userland API hooks from EDR. Requires native code (C/Rust), not pure Python. |
| Reflective loading | MEDIUM | Never touch disk — position-independent code / shellcode loading. |
| ETW/AMSI patching | WINDOWS | Blind Windows telemetry and script-scanning. Windows-specific. |
| Process injection variants | MEDIUM | Early-bird, APC, thread hijack, callback-based injection. |

> NOTE: Most in-memory evasion features require native code (C/C++/Rust). Our Python implant has fundamental limitations here. Consider a compiled implant (Go/Rust) as a future rewrite.

### D. Extensibility

| Feature | Priority | Description |
|---------|----------|-------------|
| Plugin/module system | HIGH | Drop-in Python modules for new capabilities without recompiling/redeploying core. Current codebase is monolithic. |
| Dynamic module loading | HIGH | Server sends task modules to client at runtime. Client executes them without pre-installation. |
| BOF support (Beacon Object Files) | LOW | Position-independent C programs running in-process. Requires compiled implant — not feasible with Python. |
| Command aliasing / scripting API | MEDIUM | Operator-side scripting for automation (multi-step tasks, conditional logic, loops). Similar to Aggressor Script. |

### E. Post-Exploitation Actions

| Feature | Priority | Description |
|---------|----------|-------------|
| Interactive PTY | HIGH | Full interactive shell (tab completion, color, job control) instead of one-shot command execution. |
| Screenshot capture | MEDIUM | Grab screen capture and upload to server. |
| Keylogging | MEDIUM | Background keylogger with periodic exfiltration. |
| Clipboard monitoring | LOW | Watch clipboard for passwords/tokens. |
| Webcam/audio capture | LOW | Capture from camera/mic. |
| Credential harvesting | MEDIUM | LSASS dump, SAM extraction, browser credential theft, keychain access. OS-specific implementations needed. |
| Token manipulation | WINDOWS | Steal/use Windows access tokens, make_token, pass-the-hash. |
| Privilege escalation | MEDIUM | Integrated privesc modules (kernel exploits, sudo misconfigs, SUID binaries). |
| Port scanning | MEDIUM | Built-in TCP connect/SYN scan from the implant. Avoids needing nmap on target. |
| Host discovery | MEDIUM | ARP scan, ping sweep of local subnet. |
| Persistence modules | HIGH | Registry run keys, systemd services, cron jobs, launch agents, scheduled tasks. OS-specific. |
| AD enumeration | LOW | SPN enumeration, BloodHound ingestor, LDAP queries. Windows/AD-specific. |

### F. Lateral Movement & Pivoting

| Feature | Priority | Description |
|---------|----------|-------------|
| SOCKS4/5 proxy | HIGH | Tunnel external tools (nmap, impacket, RDP) through implant into internal network. Critical for pivoting. |
| Reverse port forwarding | MEDIUM | Expose internal service back to operator via the implant. |
| Remote execution | MEDIUM | PsExec-style, WMI, WinRM, DCOM, SSH for lateral movement. |
| Spawn remote sessions | MEDIUM | Deploy implant to adjacent host via SSH/WMI/WinRM and establish new session. |

### G. Operations & Collaboration

| Feature | Priority | Description |
|---------|----------|-------------|
| Multi-operator support | MEDIUM | Multiple operators on same team server with shared session state and per-operator attribution. |
| Activity logging | HIGH | Complete log of all commands, outputs, timestamps, operator attribution. Exportable for engagement reports. |
| Payload generators | HIGH | Generate implant as EXE, DLL, service-EXE, shellcode, PowerShell one-liner, MSBuild XML, HTA. Currently only raw Python script. |
| Engagement reporting | LOW | Auto-generate PDF/HTML reports from activity logs for red team deliverables. |
| Replay / event timeline | LOW | Reconstruct engagement timeline from logs. |
| Operator authentication | MEDIUM | Team server requires login. Currently anyone with network access can interact. |

---

## Implementation Priority Order

Based on operational impact and feasibility with our Python codebase:

### Phase 1 — Core Hardening ✅ DONE
1. **Beaconing with jitter** — `c2/client/beacon.py` — `jittered_sleep()` with configurable base ± percentage
2. **Activity logging** — `c2/logging/activity_log.py` — SQLite backend (sessions, commands, events tables)
3. **Interactive PTY** — `c2/client/pty_shell.py` — `PTYSession` with `pty.fork()`, persistent shell state
4. **Persistence modules** — `c2/modules/persistence.py` — cron, systemd, registry Run, scheduled tasks
5. **Payload generators** — `generate_payload.py` + `payloads/generator.py` — PyInstaller EXE/onefile/onedir + PS stager

### Phase 2 — Traffic Evasion ✅ DONE
6. **Malleable C2 profiles** — `config/profiles/*.yaml` + `config/profile_handler.py` — URI patterns, header rotation, data hiding config
7. **URI/header randomization** — `profile_handler.py` — `build_uri()` with random suffix, `build_request_headers()` with UA/lang/referer rotation
8. **mTLS** — `c2/transport/mtls.py` — CA/cert generation via openssl, SSL contexts, SHA-256 cert pinning
9. **WebSocket transport** — `c2/transport/websocket_client.py` — async WebSocket client/server with encrypted bidirectional channel
10. **SOCKS proxy** — `c2/transport/socks_proxy.py` — SOCKS5 listener on implant, bidirectional relay to operator tools

### Phase 3 — Post-Ex Expansion ✅ DONE
11. **Plugin/module system** — `c2/modules/loader.py` — `ModuleLoader` with dynamic import, `execute_from_source()`, `list_modules()`
12. **Port scanning** — `c2/modules/portscan.py` — threaded TCP connect scan, port ranges, "common" preset
13. **Credential harvesting** — `c2/modules/credharvest.py` — Chrome/Edge Login Data, SSH keys, WiFi creds, shell history
14. **Screenshot/keylog** — `c2/modules/screenshot.py` (scrot/screencapture/GDI) + `c2/modules/keylogger.py` (GAK/evdev/pynput)
15. **Reverse port forwarding** — `c2/modules/rportfwd.py` — `ReverseForward` + `TunnelPair` for bidirectional relay

### Phase 4 — Advanced / Architecture ✅ DONE
16. **P2P / pivot links** — `c2/modules/p2p_pivot.py` — `PivotNode` for TCP chaining, pivot and leaf roles
17. **Multi-operator** — `c2/modules/multi_op.py` — `AsyncC2Server` (aiohttp) + `OperatorAuth` (SQLite token auth)
18. **DNS tunneling** — `c2/modules/dns_tunnel.py` — `DNSTunnelServer` + `DNSTunnelClient` via TXT records
19. **Compiled implant** (Go/Rust) — ❌ NOT DONE (requires separate project — Python implant limitation)
20. **Domain fronting** — `config/default.yaml` `domain_fronting` section — CDN host/real host/host header config

---

## Architecture Notes

### Current architecture limitations:
- **Singleton server pattern** — `c2_server.py` uses global state, not scalable to multi-operator
- **Synchronous HTTP** — request/response blocking, no async/concurrent operations
- **Python-only implant** — limits in-memory evasion, payload types, and stealth
- **Hardcoded config** — `settings.py` requires edit per deployment, no runtime config
- **No authentication** — no operator auth, no implant verification

### Recommended architectural changes:
- Migrate server to async framework (FastAPI/uvicorn or aiohttp)
- Add SQLite/PostgreSQL backend for session state and logging
- Introduce config file format (YAML/TOML) loaded at runtime
- Separate transport layer from command logic (abstract channel interface)
- Add operator authentication (token-based or password)
- Consider Go/Rust for a next-gen compiled implant with full EDR evasion
