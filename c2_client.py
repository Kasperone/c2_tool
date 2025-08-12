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

x = get(url='http://localhost:80', headers=HEADER, proxies=PROXY)
print(x.request.headers)