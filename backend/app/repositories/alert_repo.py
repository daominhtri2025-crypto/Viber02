from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert


def find_published(db: Session, alert_type: str, value_norm: str) -> Alert | None:
    """Chỉ trả về bản đã đăng và chưa xóa; Khách không bao giờ thấy bản nháp (FR-02)."""
    stmt = select(Alert).where(
        Alert.type == alert_type,
        Alert.value_norm == value_norm,
        Alert.status == "published",
        Alert.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def get_by_id(db: Session, alert_id: int, *, include_deleted: bool = False) -> Alert | None:
    stmt = select(Alert).where(Alert.id == alert_id)
    if not include_deleted:
        stmt = stmt.where(Alert.deleted_at.is_(None))
    return db.scalar(stmt)


def find_by_value(db: Session, alert_type: str, value_norm: str) -> Alert | None:
    """Tìm theo khóa duy nhất (type, value_norm), kể cả bản đã xóa mềm."""
    return db.scalar(select(Alert).where(Alert.type == alert_type, Alert.value_norm == value_norm))


def list_alerts(
    db: Session,
    *,
    status: str | None,
    alert_type: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Alert.status == status)
    if alert_type:
        stmt = stmt.where(Alert.type == alert_type)
    if q:
        stmt = stmt.where(Alert.search_text.contains(q.casefold(), autoescape=True))
    stmt = stmt.order_by(Alert.updated_at.desc(), Alert.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def mark_deleted(db: Session, alert: Alert, when: datetime) -> None:
    alert.deleted_at = when
    alert.status = "draft"
    alert.published_at = None
    db.commit()
