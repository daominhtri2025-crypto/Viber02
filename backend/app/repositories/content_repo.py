from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentItem


def _base(include_drafts: bool):
    stmt = select(ContentItem).where(ContentItem.deleted_at.is_(None))
    if not include_drafts:
        stmt = stmt.where(ContentItem.status == "published")
    return stmt


def list_contents(
    db: Session,
    *,
    include_drafts: bool,
    kind: str | None,
    topic: str | None,
    status: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[ContentItem]:
    stmt = _base(include_drafts)
    if kind:
        stmt = stmt.where(ContentItem.kind == kind)
    if topic:
        stmt = stmt.where(ContentItem.topic == topic)
    if status and include_drafts:
        stmt = stmt.where(ContentItem.status == status)
    if q:
        stmt = stmt.where(ContentItem.search_text.contains(q.casefold(), autoescape=True))
    stmt = stmt.order_by(ContentItem.published_at.desc().nulls_last(), ContentItem.id.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def get_content(db: Session, content_id: int, *, include_drafts: bool) -> ContentItem | None:
    return db.scalar(_base(include_drafts).where(ContentItem.id == content_id))
