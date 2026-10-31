from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert


def find_published(db: Session, alert_type: str, value_norm: str) -> Alert | None:
    """Chỉ trả về bản đã đăng; bản nháp không bao giờ hiển thị cho Khách (FR-02)."""
    stmt = select(Alert).where(
        Alert.type == alert_type,
        Alert.value_norm == value_norm,
        Alert.status == "published",
    )
    return db.scalar(stmt)
