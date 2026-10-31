import hashlib
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.crypto import decrypt_bytes, decrypt_text
from app.core.database import SessionLocal
from app.models import AuditLog, Tip, TipAttachment

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff" + b"0" * 64
CONTENT = "Có người gọi tự xưng công an yêu cầu chuyển tiền gấp."


def _create(client, content=CONTENT, category="gia_mao_co_quan", files=None):
    return client.post(
        "/api/tips",
        data={"category": category, "content": content},
        files=files or [],
    )


def test_anonymous_tip_needs_no_identity_fields(client):
    resp = _create(client)
    assert resp.status_code == 201
    code = resp.json()["tracking_code"]
    assert len(code) == 10 and code.isalnum()
    assert resp.json()["status"] == "new"


def test_only_hash_of_tracking_code_is_stored(client):
    code = _create(client).json()["tracking_code"]
    with SessionLocal() as db:
        tips = db.scalars(select(Tip)).all()
    assert len(tips) == 1
    assert tips[0].tracking_hash == hashlib.sha256(code.encode()).hexdigest()
    assert code not in tips[0].tracking_hash


def test_content_is_encrypted_at_rest(client):
    _create(client)
    with SessionLocal() as db:
        tip = db.scalars(select(Tip)).one()
    assert CONTENT.encode("utf-8") not in tip.content_enc
    assert decrypt_text(tip.content_enc) == CONTENT


def test_status_lookup_tolerates_spacing_and_case(client):
    code = _create(client).json()["tracking_code"]
    variant = code.lower()[:5] + "-" + code.lower()[5:]
    resp = client.post("/api/tips/status", json={"code": f" {variant} "})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "new"
    assert body["status_label"] == "Đã tiếp nhận"
    assert "content" not in body and "tracking_code" not in body


def test_unknown_code_returns_404(client):
    resp = client.post("/api/tips/status", json={"code": "ABCDEFGHJK"})
    assert resp.status_code == 404


def test_invalid_code_format_returns_404_not_500(client):
    resp = client.post("/api/tips/status", json={"code": "0O1I!!"})
    assert resp.status_code == 404


def test_invalid_category_and_short_content_rejected(client):
    assert _create(client, category="khong_co").status_code == 422
    assert _create(client, content="ngắn").status_code == 422


def test_attachments_are_stored_encrypted_on_disk(client):
    files = [
        ("files", ("a.png", PNG, "image/png")),
        ("files", ("b.jpg", JPG, "image/jpeg")),
    ]
    resp = _create(client, files=files)
    assert resp.status_code == 201
    with SessionLocal() as db:
        atts = db.scalars(select(TipAttachment).order_by(TipAttachment.id)).all()
    assert len(atts) == 2
    upload_root = Path(get_settings().upload_dir)
    for att, original in zip(atts, [PNG, JPG]):
        raw = (upload_root / att.file_path).read_bytes()
        assert not raw.startswith(original[:8])
        assert decrypt_bytes(raw) == original


def test_more_than_three_attachments_rejected(client):
    files = [("files", (f"{i}.png", PNG, "image/png")) for i in range(4)]
    assert _create(client, files=files).status_code == 422


def test_fake_image_with_image_extension_is_rejected(client):
    files = [("files", ("evil.png", b"<script>alert(1)</script>", "image/png"))]
    assert _create(client, files=files).status_code == 422


def test_oversized_attachment_is_rejected(client):
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    files = [("files", ("big.png", big, "image/png"))]
    assert _create(client, files=files).status_code == 413


def test_rate_limit_blocks_spam_from_same_client(client):
    limit = get_settings().tip_rate_per_hour
    for _ in range(limit):
        assert _create(client).status_code == 201
    assert _create(client).status_code == 429


def test_creation_is_audited_with_hashed_ip(client):
    _create(client)
    with SessionLocal() as db:
        entries = db.scalars(select(AuditLog).where(AuditLog.action == "tip.create")).all()
    assert len(entries) == 1
    assert entries[0].actor_id is None
    assert entries[0].ip_hash is not None and entries[0].ip_hash != "testclient"
