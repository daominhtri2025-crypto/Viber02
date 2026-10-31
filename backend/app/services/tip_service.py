"""Nghiệp vụ tố giác ẩn danh (FR-04, FR-05 phía người gửi).

Nguyên tắc: không thu danh tính; mã theo dõi chỉ tồn tại dạng băm; nội dung và ảnh mã hóa khi lưu.
"""

import re
import secrets
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.crypto import encrypt_bytes, encrypt_text
from app.core.security import sha256_hex
from app.models.tip import Tip, TipAttachment
from app.services import ratelimit
from app.services.upload_validation import UploadInvalid, detect_image

CATEGORIES = (
    "gia_mao_co_quan",   # giả mạo cơ quan chức năng
    "mua_ban_online",    # lừa đảo mua bán, sàn thương mại điện tử
    "tin_dung_den",      # app tín dụng đen
    "tuyen_dung_gia",    # lừa đảo tuyển dụng
    "khac",
)
MIN_CONTENT = 10
MAX_CONTENT = 5000
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ 0, O, 1, I để tránh nhầm lẫn
CODE_LENGTH = 10
STATUS_WINDOW_SECONDS = 300
TIP_WINDOW_SECONDS = 3600
STATUS_LABELS = {
    "new": "Đã tiếp nhận",
    "processing": "Đang xử lý",
    "done": "Đã xử lý",
}


class TipInvalid(Exception):
    pass


def normalize_code(raw: str) -> str | None:
    """Bỏ khoảng trắng và dấu gạch, đưa về chữ hoa; trả None nếu sai định dạng."""
    code = re.sub(r"[\s-]", "", raw).upper()
    if len(code) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in code):
        return None
    return code


def _new_code(db: Session) -> str:
    for _ in range(5):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        exists = db.scalar(select(Tip.id).where(Tip.tracking_hash == sha256_hex(code)))
        if exists is None:
            return code
    raise RuntimeError("Không sinh được mã theo dõi duy nhất")


def create_tip(
    db: Session,
    *,
    category: str,
    content: str,
    attachments: list[bytes],
    client_ip: str | None,
) -> str:
    """Tạo tố giác và trả về mã theo dõi (chỉ hiển thị một lần)."""
    settings = get_settings()

    if category not in CATEGORIES:
        raise TipInvalid("Loại tố giác không hợp lệ")
    text = content.strip()
    if not (MIN_CONTENT <= len(text) <= MAX_CONTENT):
        raise TipInvalid(f"Nội dung tố giác cần từ {MIN_CONTENT} đến {MAX_CONTENT} ký tự")
    if len(attachments) > settings.max_attachments_per_tip:
        raise UploadInvalid(f"Tối đa {settings.max_attachments_per_tip} ảnh cho mỗi tố giác")

    images = []
    for data in attachments:
        if not data or len(data) > settings.max_upload_bytes:
            raise UploadInvalid("Ảnh rỗng hoặc vượt quá 5 MB")
        mime, ext = detect_image(data)
        images.append((data, mime, ext))

    ip_key = sha256_hex(client_ip or "unknown")
    ratelimit.hit(db, f"tip:{ip_key}", limit=settings.tip_rate_per_hour,
                  window_seconds=TIP_WINDOW_SECONDS)

    code = _new_code(db)
    tip = Tip(
        tracking_hash=sha256_hex(code),
        category=category,
        content_enc=encrypt_text(text),
        status="new",
    )
    db.add(tip)
    db.flush()

    written: list[Path] = []
    try:
        for data, mime, ext in images:
            rel = f"tips/{tip.id}/{uuid.uuid4().hex}.{ext}.enc"
            path = Path(settings.upload_dir) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encrypt_bytes(data))
            written.append(path)
            db.add(TipAttachment(tip_id=tip.id, file_path=rel, mime=mime, size_bytes=len(data)))
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise

    record_audit(db, action="tip.create", entity="tip", entity_id=str(tip.id), client_ip=client_ip)
    return code


def get_status(db: Session, raw_code: str, *, client_ip: str | None) -> Tip | None:
    """Tra cứu tiến độ bằng mã theo dõi; có giới hạn tần suất chống dò mã."""
    settings = get_settings()
    ip_key = sha256_hex(client_ip or "unknown")
    ratelimit.hit(db, f"status:{ip_key}", limit=settings.status_lookup_limit,
                  window_seconds=STATUS_WINDOW_SECONDS)
    code = normalize_code(raw_code)
    if code is None:
        return None
    return db.scalar(select(Tip).where(Tip.tracking_hash == sha256_hex(code)))
