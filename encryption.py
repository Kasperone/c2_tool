from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from settings import KEY

def pad_key(key):
    """ This function will satisfy the Ferent encryption API requirement of having a full 32 character key. """
    while len(key) % 32 != 0:
        key += "P"
    return key

# Pad our key to 32 chars, byte encode it, urlsafe_b64 encode that, and then create the AES/CBC mode cipher object
cipher = Fernet(urlsafe_b64encode(pad_key(KEY).encode()))