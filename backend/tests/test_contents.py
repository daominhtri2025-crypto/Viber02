from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditLog


def _token(client, admin_user) -> dict:
    resp = client.post("/api/auth/login", json=admin_user)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create(client, h, **overrides):
    payload = {
        "kind": "guide",
        "title": "Nhận diện cuộc gọi giả danh công an",
        "topic": "giả mạo cơ quan",
        "body_md": "## Dấu hiệu\n\nYêu cầu chuyển khoản gấp là dấu hiệu lừa đảo.",
        "media_url": None,
    }
    payload.update(overrides)
    return client.post("/api/admin/contents", json=payload, headers=h)


def test_admin_routes_require_auth(client):
    assert client.get("/api/admin/contents").status_code == 401


def test_draft_is_hidden_from_public_then_visible_after_publish(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h).json()["id"]

    assert client.get("/api/contents").json() == []
    assert client.get(f"/api/contents/{cid}").status_code == 404

    client.post(f"/api/admin/contents/{cid}/publish", headers=h)
    listing = client.get("/api/contents").json()
    assert [x["id"] for x in listing] == [cid]
    detail = client.get(f"/api/contents/{cid}").json()
    assert "Yêu cầu chuyển khoản" in detail["body_md"]


def test_public_detail_does_not_expose_draft_fields(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h).json()["id"]
    client.post(f"/api/admin/contents/{cid}/publish", headers=h)
    summary = client.get("/api/contents").json()[0]
    assert "body_md" not in summary
    assert "status" not in summary


def test_filter_by_kind_topic_and_search(client, admin_user):
    h = _token(client, admin_user)
    a = _create(client, h).json()["id"]
    b = _create(client, h, kind="case", title="Lừa đảo việc làm online",
                topic="tuyển dụng", body_md="Đặt cọc để nhận việc là dấu hiệu lừa đảo").json()["id"]
    client.post(f"/api/admin/contents/{a}/publish", headers=h)
    client.post(f"/api/admin/contents/{b}/publish", headers=h)

    assert [x["id"] for x in client.get("/api/contents", params={"kind": "case"}).json()] == [b]
    assert [x["id"] for x in client.get("/api/contents", params={"topic": "giả mạo cơ quan"}).json()] == [a]
    assert [x["id"] for x in client.get("/api/contents", params={"q": "đặt cọc"}).json()] == [b]


def test_media_kinds_require_http_url(client, admin_user):
    h = _token(client, admin_user)
    bad = _create(client, h, kind="video", media_url="javascript:alert(1)")
    assert bad.status_code == 422
    missing = _create(client, h, kind="infographic", media_url=None)
    assert missing.status_code == 422
    ok = _create(client, h, kind="video", media_url="https://example.org/clip.mp4")
    assert ok.status_code == 201


def test_text_kinds_reject_media_url(client, admin_user):
    h = _token(client, admin_user)
    resp = _create(client, h, kind="guide", media_url="https://example.org/x.png")
    assert resp.status_code == 422


def test_update_and_soft_delete(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h).json()["id"]
    client.post(f"/api/admin/contents/{cid}/publish", headers=h)

    upd = client.patch(f"/api/admin/contents/{cid}", json={"title": "  Tiêu đề mới  "}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["title"] == "Tiêu đề mới"

    assert client.delete(f"/api/admin/contents/{cid}", headers=h).status_code == 204
    assert client.get(f"/api/contents/{cid}").status_code == 404
    assert client.get(f"/api/admin/contents/{cid}", headers=h).status_code == 404


def test_content_actions_are_audited(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h).json()["id"]
    client.post(f"/api/admin/contents/{cid}/publish", headers=h)
    with SessionLocal() as db:
        actions = {e.action for e in db.scalars(select(AuditLog)).all()}
    assert {"content.create", "content.publish"} <= actions


def test_patch_null_title_is_ignored_not_stored(client, admin_user):
    h = _token(client, admin_user)
    cid = _create(client, h).json()["id"]
    resp = client.patch(f"/api/admin/contents/{cid}", json={"title": None}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nhận diện cuộc gọi giả danh công an"


def test_missing_content_returns_404(client, admin_user):
    h = _token(client, admin_user)
    assert client.patch("/api/admin/contents/9999", json={"title": "x"}, headers=h).status_code == 404
