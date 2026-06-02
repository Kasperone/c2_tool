# C2 Tool

An HTTP-based Command and Control (C2) framework using encrypted communications.

## Setup

### 1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configure settings:
Edit `settings.py` to configure:
- **KEY**: Set a unique encryption key (32 characters or fewer)
- **ZIP_PASSWORD**: Set a strong zip encryption password
- **C2_SERVER**: Set the C2 server's IP/hostname
- **PORT**: Set the listening port (default: 80)

### 4. Start the C2 server:
```bash
python3 c2_server.py
```

### 5. Deploy the client:
Copy `c2_client.py` to the target machine and run:
```bash
python3 c2_client.py
```

### 6. Deactivate when done:
```bash
deactivate
```

## Available Commands

### Client-side commands (issued from the C2 server prompt):
- `client download <filepath>` - Transfer a file from server to client
- `client upload <filepath>` - Transfer a file from client to server
- `client zip <filepath>` - Encrypt a file on the client using AES zip
- `client unzip <filepath>` - Decrypt a zip file on the client
- `client kill` - Terminate the client
- `client sleep <seconds>` - Pause the client for a specified time
- `cd <directory>` - Change working directory on the client
- Any other command is executed as a shell command on the client

## Development

Always activate the virtual environment before working:
```bash
source venv/bin/activate
```

To add new dependencies:
```bash
pip install package_name
pip freeze > requirements.txt
```

## Security Notes

- **Always change the default KEY and ZIP_PASSWORD** before deployment
- All communications are encrypted using Fernet (AES-128-CBC)
- Client-server traffic is disguised as normal HTTP requests to appear as web traffic
- **Warning**: This tool is for authorized penetration testing and educational purposes only
