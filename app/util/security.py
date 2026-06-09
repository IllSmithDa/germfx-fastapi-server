# app/security.py
import os, hmac, hashlib, base64, re
from typing import Optional
from passlib.context import CryptContext
from cryptography.fernet import Fernet
PEPPER = os.getenv("EMAIL_PEPPER", "dev-pepper-change-me")  # set in .env
FERNET_KEY = os.getenv("FERNET_KEY")  # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
fernet = Fernet(FERNET_KEY) if FERNET_KEY else None


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

'''
def encrypt_email(email: str) -> bytes | None:
    if not fernet:
      return None
    return fernet.encrypt(email.encode())

def decrypt_email(cipher: bytes) -> str:
    if not fernet:
      raise RuntimeError("FERNET_KEY not configured")
    return fernet.decrypt(cipher).decode()
'''


def encrypt_email(email: str) -> str:
    if not fernet:
        raise RuntimeError("FERNET_KEY not configured")
    return fernet.encrypt(email.encode("utf-8")).decode("utf-8")

def decrypt_email(token: str) -> str:
    if not fernet:
        raise RuntimeError("FERNET_KEY not configured")
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")

def canonicalize_email(email: str) -> str:
    # minimum normalization; you can add domain-specific rules if you want
    return email.strip().lower()

def hex_create(message: str, key: str) -> str:
    key_bytes = key.encode("utf-8")
    msg_bytes = message.encode("utf-8")
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()


def hash_email(email: str) -> str:
    norm = canonicalize_email(email)
    return hmac.new(PEPPER.encode(), norm.encode(), hashlib.sha256).hexdigest()

def get_fernet() -> Optional[Fernet]:
    if not FERNET_KEY:
        return None
    # Expect FERNET_KEY to be a 32-byte urlsafe base64 key; generate with Fernet.generate_key()
    return Fernet(FERNET_KEY.encode("utf-8"))

