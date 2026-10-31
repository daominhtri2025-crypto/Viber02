from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RateLimit(Base):
    """Bộ đếm cửa sổ thời gian cho chống spam (khóa là chuỗi đã băm, không chứa IP rõ)."""

    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)
