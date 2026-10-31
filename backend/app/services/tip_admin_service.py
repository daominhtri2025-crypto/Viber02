"""Nghiệp vụ Admin xử lý tố giác (FR-05, NFR-05).

Mọi thao tác đọc nội dung đã giải mã đều được ghi audit. Nội dung giải mã chỉ trả về cho Admin đã xác thực.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.crypto import decrypt_bytes, decrypt_text, encrypt_text
from app.models.tip import TIP_STATUSES, Tip, TipAttachment, TipNote
from app.repositories import tip_repo

NOTE_MAX = 2000


class TipNotFound(Exception):
    pass


class TipInvalid(Exception):
    pass


def _tip_or_raise(db: Session, tip_id: int) -> Tip:
    tip = db.get(Tip, tip_id)
    if tip is None:
        raise TipNotFound()
    return tip


def list_tips(db: Session, *, status: str | None, limit: int, offset: int) -> list[tuple[Tip, int]]:
    tips = tip_repo.list_tips(db, status=status, limit=limit, offset=offset)
    counts = tip_repo.attachment_counts(db, [t.id for t in tips])
    return [(t, counts.get(t.id, 0)) for t in tips]


def get_detail(db: Session, tip_id: int, *, actor_id: int, client_ip: str | None) -> dict:
    tip = _tip_or_raise(db, tip_id)
    content = decrypt_text(tip.content_enc)
    attachments = tip_repo.list_attachments(db, tip.id)
    notes = [
        {"id": n.id, "note": decrypt_text(n.note_enc), "admin_id": n.admin_id, "created_at": n.created_at}
        for n in tip_repo.list_notes(db, tip.id)
    ]
    record_audit(db, action="tip.view", entity="tip", actor_id=actor_id,
                 entity_id=str(tip.id), client_ip=client_ip)
    return {
        "id": tip.id,
        "category": tip.category,
        "status": tip.status,
        "created_at": tip.created_at,
        "updated_at": tip.updated_at,
        "content": content,
        "attachments": attachments,
        "notes": notes,
    }


def update_status(db: Session, tip_id: int, status: str, *, actor_id: int, client_ip: str | None) -> Tip:
    if status not in TIP_STATUSES:
        raise TipInvalid("Trạng thái không hợp lệ")
    tip = _tip_or_raise(db, tip_id)
    tip.status = status
    db.commit()
    db.refresh(tip)
    record_audit(db, action="tip.status", entity="tip", actor_id=actor_id,
                 entity_id=str(tip.id), client_ip=client_ip)
    return tip


def add_note(db: Session, tip_id: int, text: str, *, actor_id: int, client_ip: str | None) -> TipNote:
    cleaned = text.strip()
    if not (1 <= len(cleaned) <= NOTE_MAX):
        raise TipInvalid(f"Ghi chú cần từ 1 đến {NOTE_MAX} ký tự")
    tip = _tip_or_raise(db, tip_id)
    note = TipNote(tip_id=tip.id, admin_id=actor_id, note_enc=encrypt_text(cleaned))
    db.add(note)
    db.commit()
    db.refresh(note)
    record_audit(db, action="tip.note", entity="tip", actor_id=actor_id,
                 entity_id=str(tip.id), client_ip=client_ip)
    return note


def read_attachment(
    db: Session,
    tip_id: int,
    attachment_id: int,
    *,
    actor_id: int,
    client_ip: str | None,
) -> tuple[bytes, str]:
    _tip_or_raise(db, tip_id)
    att = tip_repo.get_attachment(db, tip_id, attachment_id)
    if att is None:
        raise TipNotFound()

    root = Path(get_settings().upload_dir).resolve()
    path = (root / att.file_path).resolve()
    if root not in path.parents or not path.is_file():
        raise TipNotFound()  # chặn đường dẫn thoát khỏi thư mục upload

    data = decrypt_bytes(path.read_bytes())
    record_audit(db, action="tip.attachment_view", entity="tip", actor_id=actor_id,
                 entity_id=str(tip_id), client_ip=client_ip)
    return data, att.mime
