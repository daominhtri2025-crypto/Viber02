from types import SimpleNamespace

import pytest

from app.core import crypto


def test_roundtrip_text_and_bytes():
    token = crypto.encrypt_text("Tiếng Việt có dấu")
    assert crypto.decrypt_text(token) == "Tiếng Việt có dấu"
    assert crypto.decrypt_bytes(crypto.encrypt_bytes(b"\x00\x01")) == b"\x00\x01"


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(crypto, "get_settings", lambda: SimpleNamespace(fernet_key=""))
    with pytest.raises(RuntimeError):
        crypto.encrypt_text("không được lưu bản rõ")
