from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models import Alert, AuditLog, User


def _token(client, admin_user) -> dict:
    resp = client.post("/api/auth/login", json=admin_user)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create(client, headers, **overrides):
    payload = {
        "type": "phone",
        "value": "+84 901 234 567",
        "risk_level": "high",
        "description": "Giả danh cơ quan công an",
        "source_ref": "Tham chiếu cổng cảnh báo",
    }
    payload.update(overrides)
    return client.post("/api/admin/alerts", json=payload, headers=headers)


def test_admin_endpoints_require_auth(client):
    assert client.get("/api/admin/alerts").status_code == 401
    assert _create(client, {}).status_code == 401


def test_non_admin_role_is_forbidden(client):
    with SessionLocal() as db:
        guest = User(username="guest_user", password_hash=hash_password("matkhau-12345"), role="guest")
        db.add(guest)
        db.commit()
        guest_id = guest.id
    token = create_access_token(str(guest_id), "guest")
    resp = client.get("/api/admin/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_create_starts_as_draft_and_is_hidden_from_lookup(client, admin_user):
    h = _token(client, admin_user)
    resp = _create(client, h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["value_norm"] == "0901234567"
    assert client.get("/api/lookup", params={"q": "0901234567"}).json()["found"] is False


def test_publish_makes_alert_visible_then_unpublish_hides_it(client, admin_user):
    h = _token(client, admin_user)
    alert_id = _create(client, h).json()["id"]

    assert client.post(f"/api/admin/alerts/{alert_id}/publish", headers=h).json()["status"] == "published"
    assert client.get("/api/lookup", params={"q": "0901234567"}).json()["found"] is True

    assert client.post(f"/api/admin/alerts/{alert_id}/unpublish", headers=h).json()["status"] == "draft"
    assert client.get("/api/lookup", params={"q": "0901234567"}).json()["found"] is False


def test_duplicate_value_is_rejected(client, admin_user):
    h = _token(client, admin_user)
    assert _create(client, h).status_code == 201
    assert _create(client, h, value="0901234567").status_code == 409


def test_patch_renormalizes_value_and_detects_conflict(client, admin_user):
    h = _token(client, admin_user)
    first = _create(client, h).json()["id"]
    _create(client, h, value="0912345678")

    ok = client.patch(f"/api/admin/alerts/{first}", json={"value": "+84 912 345 678"}, headers=h)
    assert ok.status_code == 409  # trùng với bản ghi thứ hai

    fixed = client.patch(
        f"/api/admin/alerts/{first}", json={"value": "0977000111", "risk_level": "medium"}, headers=h
    )
    assert fixed.status_code == 200
    assert fixed.json()["value_norm"] == "0977000111"
    assert fixed.json()["risk_level"] == "medium"


def test_patch_rejects_invalid_value(client, admin_user):
    h = _token(client, admin_user)
    alert_id = _create(client, h).json()["id"]
    resp = client.patch(f"/api/admin/alerts/{alert_id}", json={"value": "abc"}, headers=h)
    assert resp.status_code == 422


def test_soft_delete_hides_alert_and_recreate_restores_it(client, admin_user):
    h = _token(client, admin_user)
    alert_id = _create(client, h).json()["id"]
    client.post(f"/api/admin/alerts/{alert_id}/publish", headers=h)

    assert client.delete(f"/api/admin/alerts/{alert_id}", headers=h).status_code == 204
    assert client.get(f"/api/admin/alerts/{alert_id}", headers=h).status_code == 404
    assert client.get("/api/lookup", params={"q": "0901234567"}).json()["found"] is False

    restored = _create(client, h, description="Khôi phục sau khi xóa mềm")
    assert restored.status_code == 201
    assert restored.json()["id"] == alert_id
    assert restored.json()["status"] == "draft"


def test_list_filters_by_status_and_excludes_deleted(client, admin_user):
    h = _token(client, admin_user)
    a = _create(client, h).json()["id"]
    _create(client, h, value="0912345678")
    client.post(f"/api/admin/alerts/{a}/publish", headers=h)

    published = client.get("/api/admin/alerts", params={"status": "published"}, headers=h).json()
    assert [x["id"] for x in published] == [a]

    client.delete(f"/api/admin/alerts/{a}", headers=h)
    remaining = client.get("/api/admin/alerts", headers=h).json()
    assert all(x["id"] != a for x in remaining)


def test_actions_are_written_to_audit_log_with_hashed_ip(client, admin_user):
    h = _token(client, admin_user)
    alert_id = _create(client, h).json()["id"]
    client.post(f"/api/admin/alerts/{alert_id}/publish", headers=h)
    client.delete(f"/api/admin/alerts/{alert_id}", headers=h)

    with SessionLocal() as db:
        actions = {e.action for e in db.scalars(select(AuditLog)).all()}
        entries = db.scalars(select(AuditLog).where(AuditLog.action == "alert.create")).all()
    assert {"login", "alert.create", "alert.publish", "alert.delete"} <= actions
    assert all(e.ip_hash != "testclient" for e in entries)


def test_missing_alert_returns_404(client, admin_user):
    h = _token(client, admin_user)
    assert client.get("/api/admin/alerts/9999", headers=h).status_code == 404
    assert client.post("/api/admin/alerts/9999/publish", headers=h).status_code == 404


def test_search_matches_vietnamese_uppercase_description(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h, description="Đòi tiền Đặt cọc qua ứng dụng").json()["id"]
    assert cid
    found = client.get("/api/admin/alerts", params={"q": "đặt cọc"}, headers=h).json()
    assert [x["id"] for x in found] == [cid]
