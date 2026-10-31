from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.alert_repo import find_published
from app.services.normalize import NormalizationError, normalize_auto


@dataclass(frozen=True)
class LookupResult:
    found: bool
    type: str | None
    value_norm: str | None
    risk_level: str | None
    description: str | None
    source_ref: str | None
    updated_at: datetime | None
    message: str


NOT_FOUND_MESSAGE = (
    "Chưa có trong danh sách cảnh báo. Điều này KHÔNG có nghĩa là an toàn; "
    "hãy đối chiếu thêm trước khi giao dịch."
)


def lookup(db: Session, raw: str) -> LookupResult:
    """Tra cứu FR-01: chuẩn hóa rồi tìm trong các cảnh báo đã đăng."""
    normalized = normalize_auto(raw)  # ném NormalizationError nếu không hợp lệ
    alert = find_published(db, normalized.type, normalized.value_norm)
    if alert is None:
        return LookupResult(
            found=False,
            type=normalized.type,
            value_norm=normalized.value_norm,
            risk_level=None,
            description=None,
            source_ref=None,
            updated_at=None,
            message=NOT_FOUND_MESSAGE,
        )
    return LookupResult(
        found=True,
        type=alert.type,
        value_norm=alert.value_norm,
        risk_level=alert.risk_level,
        description=alert.description,
        source_ref=alert.source_ref,
        updated_at=alert.updated_at,
        message="Có trong danh sách cảnh báo",
    )


__all__ = ["LookupResult", "NormalizationError", "lookup"]
