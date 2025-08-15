# Command and Control server code

from http.server import BaseHTTPRequestHandler

# Port c2 server listens on
PORT = 80

# Leave blank for binding to all interfaces, otherwise specify c2 server's IP address
BIND_ADDR = ""

class C2Handler(BaseHTTPRequestHandler):
    """This is a child class of the BaseHTTPRequestHandler class.
    It handles all HTTP requests that arrive at the c2 server."""
    

    # noinspection PyPep8Naming
    def do_GET(self):
        """ This method handles all HTTP GET requests that
        arrive at the c2 server."""

        # Sends the HTTP response code and header back to the client
        self.send_response(404)
        self.end_headers()
        pass