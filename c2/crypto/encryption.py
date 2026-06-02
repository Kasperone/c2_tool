from cryptography.fernet import Fernet, InvalidToken
from base64 import urlsafe_b64encode


def pad_key(key: str) -> str:
    while len(key) % 32 != 0:
        key += "P"
    return key


def create_cipher(key: str) -> Fernet:
    return Fernet(urlsafe_b64encode(pad_key(key).encode()))
