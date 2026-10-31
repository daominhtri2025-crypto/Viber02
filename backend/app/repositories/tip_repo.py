from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tip import Tip, TipAttachment, TipNote


def list_tips(db: Session, *, status: str | None, limit: int, offset: int) -> list[Tip]:
    stmt = select(Tip)
    if status:
        stmt = stmt.where(Tip.status == status)
    stmt = stmt.order_by(Tip.created_at.desc(), Tip.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def attachment_counts(db: Session, tip_ids: list[int]) -> dict[int, int]:
    if not tip_ids:
        return {}
    rows = db.execute(
        select(TipAttachment.tip_id, func.count(TipAttachment.id))
        .where(TipAttachment.tip_id.in_(tip_ids))
        .group_by(TipAttachment.tip_id)
    ).all()
    return {tip_id: count for tip_id, count in rows}


def list_attachments(db: Session, tip_id: int) -> list[TipAttachment]:
    return list(db.scalars(
        select(TipAttachment).where(TipAttachment.tip_id == tip_id).order_by(TipAttachment.id)
    ))


def get_attachment(db: Session, tip_id: int, attachment_id: int) -> TipAttachment | None:
    return db.scalar(
        select(TipAttachment).where(
            TipAttachment.id == attachment_id, TipAttachment.tip_id == tip_id
        )
    )


def list_notes(db: Session, tip_id: int) -> list[TipNote]:
    return list(db.scalars(
        select(TipNote).where(TipNote.tip_id == tip_id).order_by(TipNote.created_at, TipNote.id)
    ))
