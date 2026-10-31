from sqlalchemy import select

from app.core.crypto import decrypt_text
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models import AuditLog, TipNote, User

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
CONTENT = "Nạn nhân được yêu cầu đặt cọc qua ví điện tử."


def _admin_headers(client, admin_user) -> dict:
    resp = client.post("/api/auth/login", json=admin_user)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _submit_tip(client, files=None) -> str:
    resp = client.post(
        "/api/tips",
        data={"category": "tin_dung_den", "content": CONTENT},
        files=files or [],
    )
    assert resp.status_code == 201
    return resp.json()["tracking_code"]


def _first_tip_id(client, h) -> int:
    return client.get("/api/admin/tips", headers=h).json()[0]["id"]


def test_admin_tip_routes_require_auth(client):
    assert client.get("/api/admin/tips").status_code == 401


def test_guest_role_is_forbidden(client):
    with SessionLocal() as db:
        guest = User(username="guest2", password_hash=hash_password("matkhau-12345"), role="guest")
        db.add(guest)
        db.commit()
        guest_id = guest.id
    token = create_access_token(str(guest_id), "guest")
    resp = client.get("/api/admin/tips", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_list_shows_new_tips_with_attachment_count_and_filters(client, admin_user):
    _submit_tip(client, files=[("files", ("a.png", PNG, "image/png"))])
    h = _admin_headers(client, admin_user)
    rows = client.get("/api/admin/tips", headers=h).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "new"
    assert rows[0]["attachment_count"] == 1
    assert client.get("/api/admin/tips", params={"status": "done"}, headers=h).json() == []


def test_detail_decrypts_content_and_is_audited(client, admin_user):
    _submit_tip(client)
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    body = client.get(f"/api/admin/tips/{tip_id}", headers=h).json()
    assert body["content"] == CONTENT
    with SessionLocal() as db:
        views = db.scalars(select(AuditLog).where(AuditLog.action == "tip.view")).all()
    assert len(views) == 1 and views[0].ip_hash is not None


def test_status_change_is_reflected_in_public_lookup(client, admin_user):
    code = _submit_tip(client)
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)

    upd = client.patch(f"/api/admin/tips/{tip_id}/status", json={"status": "processing"}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["status"] == "processing"

    public = client.post("/api/tips/status", json={"code": code}).json()
    assert public["status"] == "processing"
    assert public["status_label"] == "Đang xử lý"


def test_invalid_status_rejected(client, admin_user):
    _submit_tip(client)
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    resp = client.patch(f"/api/admin/tips/{tip_id}/status", json={"status": "deleted"}, headers=h)
    assert resp.status_code == 422


def test_note_is_encrypted_at_rest_and_listed(client, admin_user):
    _submit_tip(client)
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    text = "Đã liên hệ đơn vị chuyên trách, chờ phản hồi."
    resp = client.post(f"/api/admin/tips/{tip_id}/notes", json={"note": text}, headers=h)
    assert resp.status_code == 201

    with SessionLocal() as db:
        stored = db.scalars(select(TipNote)).one()
    assert text.encode("utf-8") not in stored.note_enc
    assert decrypt_text(stored.note_enc) == text

    detail = client.get(f"/api/admin/tips/{tip_id}", headers=h).json()
    assert [n["note"] for n in detail["notes"]] == [text]


def test_empty_note_rejected(client, admin_user):
    _submit_tip(client)
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    assert client.post(f"/api/admin/tips/{tip_id}/notes", json={"note": "   "}, headers=h).status_code == 422


def test_attachment_download_returns_original_bytes_and_is_audited(client, admin_user):
    _submit_tip(client, files=[("files", ("a.png", PNG, "image/png"))])
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    detail = client.get(f"/api/admin/tips/{tip_id}", headers=h).json()
    att_id = detail["attachments"][0]["id"]

    resp = client.get(f"/api/admin/tips/{tip_id}/attachments/{att_id}", headers=h)
    assert resp.status_code == 200
    assert resp.content == PNG
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["cache-control"] == "no-store"
    with SessionLocal() as db:
        views = db.scalars(select(AuditLog).where(AuditLog.action == "tip.attachment_view")).all()
    assert len(views) == 1


def test_attachment_from_other_tip_is_not_found(client, admin_user):
    _submit_tip(client, files=[("files", ("a.png", PNG, "image/png"))])
    _submit_tip(client)
    h = _admin_headers(client, admin_user)
    rows = client.get("/api/admin/tips", headers=h).json()
    with_att = next(r["id"] for r in rows if r["attachment_count"] == 1)
    without_att = next(r["id"] for r in rows if r["attachment_count"] == 0)
    att_id = client.get(f"/api/admin/tips/{with_att}", headers=h).json()["attachments"][0]["id"]
    resp = client.get(f"/api/admin/tips/{without_att}/attachments/{att_id}", headers=h)
    assert resp.status_code == 404


def test_missing_tip_returns_404(client, admin_user):
    h = _admin_headers(client, admin_user)
    assert client.get("/api/admin/tips/9999", headers=h).status_code == 404
    assert client.patch("/api/admin/tips/9999/status", json={"status": "done"}, headers=h).status_code == 404


def test_attachment_path_outside_upload_root_is_refused(client, admin_user):
    _submit_tip(client, files=[("files", ("a.png", PNG, "image/png"))])
    h = _admin_headers(client, admin_user)
    tip_id = _first_tip_id(client, h)
    att_id = client.get(f"/api/admin/tips/{tip_id}", headers=h).json()["attachments"][0]["id"]

    from app.models import TipAttachment
    with SessionLocal() as db:
        att = db.get(TipAttachment, att_id)
        att.file_path = "../../etc/passwd"
        db.commit()
    resp = client.get(f"/api/admin/tips/{tip_id}/attachments/{att_id}", headers=h)
    assert resp.status_code == 404
