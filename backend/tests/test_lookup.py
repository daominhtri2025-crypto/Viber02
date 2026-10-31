from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Alert


def _seed(**overrides) -> None:
    base = dict(
        type="phone",
        value_norm="0901234567",
        value_display="0901234567",
        risk_level="high",
        description="Giả danh cơ quan công an yêu cầu chuyển khoản",
        source_ref="Cổng cảnh báo quốc gia (tham chiếu)",
        status="published",
        published_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    with SessionLocal() as db:  # type: Session
        db.add(Alert(**base))
        db.commit()


def test_found_published_alert(client):
    _seed()
    resp = client.get("/api/lookup", params={"q": "+84 901 234 567"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["type"] == "phone"
    assert body["value_norm"] == "0901234567"
    assert body["risk_level"] == "high"
    assert body["source_ref"].startswith("Cổng cảnh báo")


def test_draft_alert_is_not_visible(client):
    _seed(status="draft")
    body = client.get("/api/lookup", params={"q": "0901234567"}).json()
    assert body["found"] is False


def test_not_found_never_claims_safety(client):
    body = client.get("/api/lookup", params={"q": "https://tot-lanh-manh.vn"}).json()
    assert body["found"] is False
    assert "KHÔNG có nghĩa là an toàn" in body["message"]


def test_url_lookup_matches_normalized_host(client):
    _seed(type="url", value_norm="bank-fake.xyz", value_display="bank-fake.xyz")
    body = client.get("/api/lookup", params={"q": "https://www.BANK-FAKE.xyz/login?ref=1"}).json()
    assert body["found"] is True
    assert body["type"] == "url"


def test_invalid_input_returns_422(client):
    resp = client.get("/api/lookup", params={"q": "12"})
    assert resp.status_code == 422


def test_empty_query_returns_422(client):
    resp = client.get("/api/lookup", params={"q": "   "})
    assert resp.status_code == 422


def test_missing_query_returns_422(client):
    resp = client.get("/api/lookup")
    assert resp.status_code == 422
