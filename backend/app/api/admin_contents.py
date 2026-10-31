from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories import content_repo
from app.services import content_service
from app.services.content_service import ContentInvalid, ContentNotFound

router = APIRouter(prefix="/api/admin/contents", tags=["admin-contents"])

Kind = Literal["guide", "case", "infographic", "video"]


class ContentIn(BaseModel):
    kind: Kind
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field("", max_length=64)
    body_md: str = Field("", max_length=50_000)
    media_url: str | None = Field(None, max_length=500)


class ContentPatch(BaseModel):
    kind: Kind | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    topic: str | None = Field(None, max_length=64)
    body_md: str | None = Field(None, max_length=50_000)
    media_url: str | None = Field(None, max_length=500)


class ContentAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    topic: str
    body_md: str
    media_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, ContentNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy nội dung")
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("", response_model=ContentAdminOut, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentIn,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        return content_service.create_content(
            db, actor_id=admin.id, client_ip=_ip(request), kind=payload.kind,
            title=payload.title, topic=payload.topic, body_md=payload.body_md,
            media_url=payload.media_url,
        )
    except ContentInvalid as exc:
        raise _http(exc)


@router.get("", response_model=list[ContentAdminOut])
def list_contents(
    status_filter: Literal["draft", "published"] | None = Query(None, alias="status"),
    kind: Kind | None = Query(None),
    topic: str | None = Query(None, max_length=64),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return content_repo.list_contents(
        db, include_drafts=True, kind=kind, topic=topic, status=status_filter,
        q=q, limit=limit, offset=offset,
    )


@router.get("/{content_id}", response_model=ContentAdminOut)
def get_content(content_id: int, _: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        return content_service.get_content_admin(db, content_id)
    except ContentNotFound as exc:
        raise _http(exc)


@router.patch("/{content_id}", response_model=ContentAdminOut)
def update_content(
    content_id: int,
    payload: ContentPatch,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    try:
        return content_service.update_content(
            db, content_id, actor_id=admin.id, client_ip=_ip(request), changes=changes
        )
    except (ContentNotFound, ContentInvalid) as exc:
        raise _http(exc)


@router.post("/{content_id}/publish", response_model=ContentAdminOut)
def publish_content(
    content_id: int, request: Request,
    admin: User = Depends(get_current_admin), db: Session = Depends(get_db),
):
    try:
        return content_service.set_published(
            db, content_id, publish=True, actor_id=admin.id, client_ip=_ip(request)
        )
    except ContentNotFound as exc:
        raise _http(exc)


@router.post("/{content_id}/unpublish", response_model=ContentAdminOut)
def unpublish_content(
    content_id: int, request: Request,
    admin: User = Depends(get_current_admin), db: Session = Depends(get_db),
):
    try:
        return content_service.set_published(
            db, content_id, publish=False, actor_id=admin.id, client_ip=_ip(request)
        )
    except ContentNotFound as exc:
        raise _http(exc)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    content_id: int, request: Request,
    admin: User = Depends(get_current_admin), db: Session = Depends(get_db),
):
    try:
        content_service.soft_delete_content(
            db, content_id, actor_id=admin.id, client_ip=_ip(request)
        )
    except ContentNotFound as exc:
        raise _http(exc)
