from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.services import tip_service
from app.services.ratelimit import RateLimited
from app.services.upload_validation import UploadInvalid

router = APIRouter(prefix="/api/tips", tags=["tips"])


class TipCreatedOut(BaseModel):
    tracking_code: str
    status: str
    message: str


class TipStatusIn(BaseModel):
    # Dùng JSON body thay vì query string để mã theo dõi không xuất hiện trong URL/log.
    code: str = Field(..., min_length=1, max_length=32)


class TipStatusOut(BaseModel):
    status: str
    status_label: str
    created_at: datetime
    updated_at: datetime


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", response_model=TipCreatedOut, status_code=status.HTTP_201_CREATED)
def create_tip(
    request: Request,
    category: str = Form(..., max_length=32),
    content: str = Form(..., max_length=5000),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if len(files) > settings.max_attachments_per_tip:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Tối đa {settings.max_attachments_per_tip} ảnh cho mỗi tố giác")

    blobs: list[bytes] = []
    for upload in files:
        data = upload.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Ảnh vượt quá 5 MB")
        blobs.append(data)

    try:
        code = tip_service.create_tip(
            db, category=category, content=content, attachments=blobs, client_ip=_ip(request)
        )
    except RateLimited:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Bạn đã gửi quá nhiều tố giác trong thời gian ngắn. Vui lòng thử lại sau.")
    except (tip_service.TipInvalid, UploadInvalid) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    return TipCreatedOut(
        tracking_code=code,
        status="new",
        message="Vui lòng lưu mã theo dõi này. Mã chỉ hiển thị một lần.",
    )


@router.post("/status", response_model=TipStatusOut)
def tip_status(payload: TipStatusIn, request: Request, db: Session = Depends(get_db)):
    try:
        tip = tip_service.get_status(db, payload.code, client_ip=_ip(request))
    except RateLimited:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Tra cứu quá nhiều, vui lòng thử lại sau")
    if tip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy mã theo dõi")
    return TipStatusOut(
        status=tip.status,
        status_label=tip_service.STATUS_LABELS.get(tip.status, tip.status),
        created_at=tip.created_at,
        updated_at=tip.updated_at,
    )
