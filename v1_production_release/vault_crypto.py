from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hashlib, json

def _kdf(password: bytes, salt: bytes, dklen: int = 32) -> bytes:
    return PBKDF2(password, salt, dkLen=dklen, count=200_000, hmac_hash_module=hashlib.sha256)

def encrypt_vault_bytes(plaintext: bytes, password: str) -> bytes:
    salt  = get_random_bytes(16)
    key   = _kdf(password.encode("utf-8"), salt)
    cipher= AES.new(key, AES.MODE_GCM)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    obj = {
        "v": 1,
        "alg": "AES-256-GCM",
        "salt":  salt.hex(),
        "nonce": cipher.nonce.hex(),
        "ct":    ct.hex(),
        "tag":   tag.hex(),
    }
    return json.dumps(obj, separators=(",",":")).encode("utf-8")
