from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import content_repo

router = APIRouter(prefix="/api/contents", tags=["contents"])


class ContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    topic: str
    body_md: str
    media_url: str | None
    published_at: datetime | None
    updated_at: datetime


class ContentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    topic: str
    media_url: str | None
    published_at: datetime | None


@router.get("", response_model=list[ContentSummary])
def list_contents(
    kind: Literal["guide", "case", "infographic", "video"] | None = Query(None),
    topic: str | None = Query(None, max_length=64),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return content_repo.list_contents(
        db, include_drafts=False, kind=kind, topic=topic, status=None,
        q=q, limit=limit, offset=offset,
    )


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: int, db: Session = Depends(get_db)):
    item = content_repo.get_content(db, content_id, include_drafts=False)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy nội dung")
    return item
