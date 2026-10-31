from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow

ALERT_TYPES = ("account", "phone", "url")
RISK_LEVELS = ("high", "medium", "low")
ALERT_STATUSES = ("draft", "published")


class Alert(Base):
    """Cảnh báo lừa đảo do Admin nhập và biên tập (SRS mục 1, FR-02)."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("type", "value_norm", name="uq_alerts_type_value"),
        Index("ix_alerts_lookup", "type", "value_norm", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    value_norm: Mapped[str] = mapped_column(String(253))
    value_display: Mapped[str] = mapped_column(String(253))
    risk_level: Mapped[str] = mapped_column(String(8), default="high")
    description: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
