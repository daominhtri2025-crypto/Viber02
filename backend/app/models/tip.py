from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow

TIP_STATUSES = ("new", "processing", "done")


class Tip(Base):
    """Tố giác ẩn danh. Không lưu họ tên, SĐT, CCCD; mã theo dõi chỉ lưu dạng băm (FR-04)."""

    __tablename__ = "tips"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32))
    content_enc: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(16), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TipNote(Base):
    """Ghi chú nội bộ của Admin về một tố giác; nội dung mã hóa khi lưu."""

    __tablename__ = "tip_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tip_id: Mapped[int] = mapped_column(ForeignKey("tips.id", ondelete="CASCADE"), index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note_enc: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TipAttachment(Base):
    """Ảnh đính kèm đã mã hóa trên đĩa; chỉ lưu đường dẫn tương đối."""

    __tablename__ = "tip_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tip_id: Mapped[int] = mapped_column(ForeignKey("tips.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
