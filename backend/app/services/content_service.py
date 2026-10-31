"""Nghiệp vụ quản lý nội dung tuyên truyền cho Admin (FR-03, NFR-05)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.content import CONTENT_KINDS, ContentItem
from app.repositories import content_repo

MEDIA_KINDS = ("infographic", "video")


class ContentNotFound(Exception):
    pass


class ContentInvalid(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _search_text(title: str, body_md: str) -> str:
    return f"{title}\n{body_md}".casefold()


def validate_payload(kind: str, media_url: str | None) -> None:
    if kind not in CONTENT_KINDS:
        raise ContentInvalid("Loại nội dung không hợp lệ")
    if kind in MEDIA_KINDS:
        if not media_url or not media_url.startswith(("https://", "http://")):
            raise ContentInvalid("Infographic/video cần liên kết http(s) hợp lệ")
    elif media_url:
        raise ContentInvalid("Cẩm nang và tình huống không đính kèm liên kết media")


def create_content(
    db: Session,
    *,
    actor_id: int,
    client_ip: str | None,
    kind: str,
    title: str,
    topic: str,
    body_md: str,
    media_url: str | None,
) -> ContentItem:
    validate_payload(kind, media_url)
    item = ContentItem(
        kind=kind,
        title=title.strip(),
        topic=topic.strip(),
        body_md=body_md,
        search_text=_search_text(title.strip(), body_md),
        media_url=media_url,
        status="draft",
        created_by=actor_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_audit(db, action="content.create", entity="content", actor_id=actor_id,
                 entity_id=str(item.id), client_ip=client_ip)
    return item


def get_content_admin(db: Session, content_id: int) -> ContentItem:
    item = content_repo.get_content(db, content_id, include_drafts=True)
    if item is None:
        raise ContentNotFound()
    return item


def update_content(
    db: Session,
    content_id: int,
    *,
    actor_id: int,
    client_ip: str | None,
    changes: dict,
) -> ContentItem:
    item = get_content_admin(db, content_id)
    kind = changes.get("kind", item.kind)
    media_url = changes["media_url"] if "media_url" in changes else item.media_url
    validate_payload(kind, media_url)

    for field in ("kind", "title", "topic", "body_md", "media_url"):
        if field not in changes:
            continue
        value = changes[field]
        if value is None and field != "media_url":
            continue  # các trường không cho phép null: bỏ qua giá trị rỗng
        if isinstance(value, str) and field in ("title", "topic"):
            value = value.strip()
        setattr(item, field, value)

    item.search_text = _search_text(item.title, item.body_md)
    db.commit()
    db.refresh(item)
    record_audit(db, action="content.update", entity="content", actor_id=actor_id,
                 entity_id=str(item.id), client_ip=client_ip)
    return item


def set_published(
    db: Session,
    content_id: int,
    *,
    publish: bool,
    actor_id: int,
    client_ip: str | None,
) -> ContentItem:
    item = get_content_admin(db, content_id)
    item.status = "published" if publish else "draft"
    item.published_at = _now() if publish else None
    db.commit()
    db.refresh(item)
    action = "content.publish" if publish else "content.unpublish"
    record_audit(db, action=action, entity="content", actor_id=actor_id,
                 entity_id=str(item.id), client_ip=client_ip)
    return item


def soft_delete_content(
    db: Session,
    content_id: int,
    *,
    actor_id: int,
    client_ip: str | None,
) -> None:
    item = get_content_admin(db, content_id)
    item.deleted_at = _now()
    item.status = "draft"
    item.published_at = None
    db.commit()
    record_audit(db, action="content.delete", entity="content", actor_id=actor_id,
                 entity_id=str(item.id), client_ip=client_ip)
