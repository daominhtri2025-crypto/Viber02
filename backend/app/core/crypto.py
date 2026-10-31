"""Mã hóa đối xứng Fernet (AES-128-CBC + HMAC) cho dữ liệu tố giác khi lưu (NFR-03).

Fail-closed: nếu chưa cấu hình FERNET_KEY thì từ chối ghi dữ liệu, không lưu bản rõ.
"""

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise RuntimeError("FERNET_KEY chưa được cấu hình; từ chối lưu dữ liệu tố giác")
    return Fernet(key.encode("utf-8"))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def encrypt_text(text: str) -> bytes:
    return encrypt_bytes(text.encode("utf-8"))


def decrypt_text(token: bytes) -> str:
    return decrypt_bytes(token).decode("utf-8")
