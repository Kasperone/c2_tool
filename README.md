# C2 Tool

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

### 3. Run the project:
```bash
python3 your_main_file.py
```

### 4. Deactivate when done:
```bash
deactivate
```

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

## Docker Setup

### Option 1: Using Docker Compose (Recommended)
```bash
# Build and run both server and client
docker-compose up --build

# Run only the server
docker-compose up c2-server

# Run only the client
docker-compose up c2-client
```

### Option 2: Using Docker directly
```bash
# Build the image
docker build -t c2_tool .

# Run the server
docker run -p 8080:8080 -v $(pwd):/app/c2_tool c2_tool python3 c2_server.py

# Run the client (in another terminal)
docker run -v $(pwd):/app/c2_tool c2_tool python3 c2_client.py
```

### Option 3: Interactive shell in container
```bash
# Get a shell inside the container
docker run -it -v $(pwd):/app/c2_tool c2_tool /bin/bash

# Then run your scripts
python3 c2_server.py
```
