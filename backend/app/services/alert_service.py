"""Nghiệp vụ quản lý cảnh báo cho Admin (FR-02, NFR-05)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.alert import Alert
from app.repositories import alert_repo
from app.services.normalize import normalize_for_type


class AlertNotFound(Exception):
    pass


class AlertConflict(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_alert(
    db: Session,
    *,
    actor_id: int,
    client_ip: str | None,
    alert_type: str,
    value: str,
    risk_level: str,
    description: str,
    source_ref: str,
) -> Alert:
    value_norm = normalize_for_type(alert_type, value)
    existing = alert_repo.find_by_value(db, alert_type, value_norm)
    if existing is not None and existing.deleted_at is None:
        raise AlertConflict("Cảnh báo cho giá trị này đã tồn tại")

    if existing is not None:
        # Khôi phục bản đã xóa mềm thay vì vi phạm khóa duy nhất (type, value_norm).
        alert = existing
        alert.deleted_at = None
    else:
        alert = Alert(type=alert_type, value_norm=value_norm)
        db.add(alert)

    alert.value_display = value.strip()
    alert.risk_level = risk_level
    alert.description = description
    alert.source_ref = source_ref
    alert.status = "draft"
    alert.published_at = None
    alert.created_by = actor_id
    db.commit()
    db.refresh(alert)

    record_audit(db, action="alert.create", entity="alert", actor_id=actor_id,
                 entity_id=str(alert.id), client_ip=client_ip)
    return alert


def get_alert(db: Session, alert_id: int) -> Alert:
    alert = alert_repo.get_by_id(db, alert_id)
    if alert is None:
        raise AlertNotFound()
    return alert


def update_alert(
    db: Session,
    alert_id: int,
    *,
    actor_id: int,
    client_ip: str | None,
    changes: dict,
) -> Alert:
    alert = get_alert(db, alert_id)

    if "value" in changes or "type" in changes:
        new_type = changes.get("type", alert.type)
        raw_value = changes.get("value", alert.value_display)
        new_norm = normalize_for_type(new_type, raw_value)
        clash = alert_repo.find_by_value(db, new_type, new_norm)
        if clash is not None and clash.id != alert.id:
            raise AlertConflict("Giá trị này đã có cảnh báo khác")
        alert.type = new_type
        alert.value_norm = new_norm
        alert.value_display = raw_value.strip()

    for field in ("risk_level", "description", "source_ref"):
        if field in changes and changes[field] is not None:
            setattr(alert, field, changes[field])

    db.commit()
    db.refresh(alert)
    record_audit(db, action="alert.update", entity="alert", actor_id=actor_id,
                 entity_id=str(alert.id), client_ip=client_ip)
    return alert


def set_published(
    db: Session,
    alert_id: int,
    *,
    publish: bool,
    actor_id: int,
    client_ip: str | None,
) -> Alert:
    alert = get_alert(db, alert_id)
    if publish:
        alert.status = "published"
        alert.published_at = _now()
    else:
        alert.status = "draft"
        alert.published_at = None
    db.commit()
    db.refresh(alert)
    action = "alert.publish" if publish else "alert.unpublish"
    record_audit(db, action=action, entity="alert", actor_id=actor_id,
                 entity_id=str(alert.id), client_ip=client_ip)
    return alert


def soft_delete_alert(
    db: Session,
    alert_id: int,
    *,
    actor_id: int,
    client_ip: str | None,
) -> None:
    alert = get_alert(db, alert_id)
    alert_repo.mark_deleted(db, alert, _now())
    record_audit(db, action="alert.delete", entity="alert", actor_id=actor_id,
                 entity_id=str(alert.id), client_ip=client_ip)
