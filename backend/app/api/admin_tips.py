from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories import tip_repo
from app.services import tip_admin_service
from app.services.tip_admin_service import TipInvalid, TipNotFound

router = APIRouter(prefix="/api/admin/tips", tags=["admin-tips"])

TipStatus = Literal["new", "processing", "done"]


class TipSummaryOut(BaseModel):
    id: int
    category: str
    status: str
    created_at: datetime
    updated_at: datetime
    attachment_count: int


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mime: str
    size_bytes: int
    created_at: datetime


class NoteOut(BaseModel):
    id: int
    note: str
    admin_id: int | None
    created_at: datetime


class TipDetailOut(BaseModel):
    id: int
    category: str
    status: str
    created_at: datetime
    updated_at: datetime
    content: str
    attachments: list[AttachmentOut]
    notes: list[NoteOut]


class StatusIn(BaseModel):
    status: TipStatus


class NoteIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, TipNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy tố giác")
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("", response_model=list[TipSummaryOut])
def list_tips(
    status_filter: TipStatus | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = tip_admin_service.list_tips(db, status=status_filter, limit=limit, offset=offset)
    return [
        TipSummaryOut(
            id=t.id, category=t.category, status=t.status, created_at=t.created_at,
            updated_at=t.updated_at, attachment_count=count,
        )
        for t, count in rows
    ]


@router.get("/{tip_id}", response_model=TipDetailOut)
def get_tip(
    tip_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        detail = tip_admin_service.get_detail(db, tip_id, actor_id=admin.id, client_ip=_ip(request))
    except TipNotFound as exc:
        raise _http(exc)
    return detail


@router.patch("/{tip_id}/status", response_model=TipSummaryOut)
def update_status(
    tip_id: int,
    payload: StatusIn,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        tip = tip_admin_service.update_status(
            db, tip_id, payload.status, actor_id=admin.id, client_ip=_ip(request)
        )
    except (TipNotFound, TipInvalid) as exc:
        raise _http(exc)
    count = tip_repo.attachment_counts(db, [tip.id]).get(tip.id, 0)
    return TipSummaryOut(
        id=tip.id, category=tip.category, status=tip.status, created_at=tip.created_at,
        updated_at=tip.updated_at, attachment_count=count,
    )


@router.post("/{tip_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    tip_id: int,
    payload: NoteIn,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        note = tip_admin_service.add_note(
            db, tip_id, payload.note, actor_id=admin.id, client_ip=_ip(request)
        )
    except (TipNotFound, TipInvalid) as exc:
        raise _http(exc)
    return NoteOut(id=note.id, note=payload.note.strip(), admin_id=note.admin_id, created_at=note.created_at)


@router.get("/{tip_id}/attachments/{attachment_id}")
def download_attachment(
    tip_id: int,
    attachment_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        data, mime = tip_admin_service.read_attachment(
            db, tip_id, attachment_id, actor_id=admin.id, client_ip=_ip(request)
        )
    except TipNotFound as exc:
        raise _http(exc)
    ext = "jpg" if mime == "image/jpeg" else "png"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="tip-{tip_id}-{attachment_id}.{ext}"',
        },
    )
