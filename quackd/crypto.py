import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib


def fernet_keygen(key):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'\xe4(\x7f)FQWM:cOW\x97\x86\xe7\x86',
        iterations=390000,
    )
    return base64.urlsafe_b64encode(kdf.derive(key.encode('utf-8')))


def sha3_digest(key):
    sha3 = hashlib.sha3_512()
    sha3.update(str.encode(key))
    return sha3.hexdigest()


def encrypt_text(text, key):
    fernet = Fernet(key)
    return fernet.encrypt(text.encode('utf-8'))


def decrypt_text(text, key):
    fernet = Fernet(key)
    return fernet.decrypt(text).decode('utf-8')
