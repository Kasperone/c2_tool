from os import chdir, getcwd, path
from subprocess import run, PIPE, STDOUT


def run_shell_command(command: str) -> str:
    result = run(command, shell=True, stdout=PIPE, stderr=STDOUT)
    return result.stdout.decode(errors="replace")


def change_directory(directory: str) -> tuple[bool, str]:
    try:
        chdir(directory)
        return True, getcwd()
    except FileNotFoundError:
        return False, f"Directory {directory} not found"
    except NotADirectoryError:
        return False, f"{directory} is not a directory"
    except PermissionError:
        return False, f"Permission denied: {directory}"
    except OSError as e:
        return False, f"Error accessing {directory}: {e}"
