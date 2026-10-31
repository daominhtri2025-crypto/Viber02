"""Giới hạn tần suất theo cửa sổ thời gian (chống spam tố giác và dò mã theo dõi)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ratelimit import RateLimit
from app.models.user import utcnow


class RateLimited(Exception):
    pass


def _as_utc(dt: datetime) -> datetime:
    # SQLite trả về datetime không có tzinfo; coi đó là UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def hit(db: Session, key: str, *, limit: int, window_seconds: int) -> None:
    """Ghi nhận một lượt; ném RateLimited nếu vượt ngưỡng trong cửa sổ hiện tại."""
    now = utcnow()
    row = db.get(RateLimit, key)
    if row is None:
        row = RateLimit(key=key, window_start=now, count=0)
        db.add(row)
    elif _as_utc(row.window_start) + timedelta(seconds=window_seconds) <= now:
        row.window_start = now
        row.count = 0
    row.count += 1
    db.commit()
    if row.count > limit:
        raise RateLimited()
