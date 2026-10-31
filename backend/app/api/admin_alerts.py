from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories import alert_repo
from app.services import alert_service
from app.services.alert_service import AlertConflict, AlertNotFound
from app.services.normalize import NormalizationError

router = APIRouter(prefix="/api/admin/alerts", tags=["admin-alerts"])

AlertType = Literal["account", "phone", "url"]
RiskLevel = Literal["high", "medium", "low"]


class AlertIn(BaseModel):
    type: AlertType
    value: str = Field(..., min_length=1, max_length=253)
    risk_level: RiskLevel = "high"
    description: str = Field("", max_length=4000)
    source_ref: str = Field("", max_length=500)


class AlertPatch(BaseModel):
    type: AlertType | None = None
    value: str | None = Field(None, min_length=1, max_length=253)
    risk_level: RiskLevel | None = None
    description: str | None = Field(None, max_length=4000)
    source_ref: str | None = Field(None, max_length=500)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value_norm: str
    value_display: str
    risk_level: str
    description: str
    source_ref: str
    status: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _map_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, AlertNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy cảnh báo")
    if isinstance(exc, AlertConflict):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, NormalizationError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    raise exc


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertIn,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        return alert_service.create_alert(
            db,
            actor_id=admin.id,
            client_ip=_client_ip(request),
            alert_type=payload.type,
            value=payload.value,
            risk_level=payload.risk_level,
            description=payload.description,
            source_ref=payload.source_ref,
        )
    except (AlertConflict, NormalizationError) as exc:
        raise _map_errors(exc)


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status_filter: Literal["draft", "published"] | None = Query(None, alias="status"),
    type_filter: AlertType | None = Query(None, alias="type"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return alert_repo.list_alerts(
        db, status=status_filter, alert_type=type_filter, q=q, limit=limit, offset=offset
    )


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, _: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        return alert_service.get_alert(db, alert_id)
    except AlertNotFound as exc:
        raise _map_errors(exc)


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertPatch,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    try:
        return alert_service.update_alert(
            db, alert_id, actor_id=admin.id, client_ip=_client_ip(request), changes=changes
        )
    except (AlertNotFound, AlertConflict, NormalizationError) as exc:
        raise _map_errors(exc)


@router.post("/{alert_id}/publish", response_model=AlertOut)
def publish_alert(
    alert_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        return alert_service.set_published(
            db, alert_id, publish=True, actor_id=admin.id, client_ip=_client_ip(request)
        )
    except AlertNotFound as exc:
        raise _map_errors(exc)


@router.post("/{alert_id}/unpublish", response_model=AlertOut)
def unpublish_alert(
    alert_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        return alert_service.set_published(
            db, alert_id, publish=False, actor_id=admin.id, client_ip=_client_ip(request)
        )
    except AlertNotFound as exc:
        raise _map_errors(exc)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        alert_service.soft_delete_alert(
            db, alert_id, actor_id=admin.id, client_ip=_client_ip(request)
        )
    except AlertNotFound as exc:
        raise _map_errors(exc)
