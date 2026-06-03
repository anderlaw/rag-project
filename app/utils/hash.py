import hashlib


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
