"""Parola özeti, oturum kimliği özeti ve servis kimlik bilgisi şifreleme. Saf yardımcılar."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> tuple[str, str]:
    """(istemciye verilen değer, veritabanında saklanan özet)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def encrypt_value(key: str, plaintext: str) -> bytes:
    return Fernet(key.encode()).encrypt(plaintext.encode())


def decrypt_value(key: str, ciphertext: bytes) -> str:
    return Fernet(key.encode()).decrypt(ciphertext).decode()
