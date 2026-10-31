from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.lookup import lookup
from app.services.normalize import NormalizationError

router = APIRouter(prefix="/api", tags=["lookup"])


class LookupOut(BaseModel):
    found: bool
    type: str | None
    value_norm: str | None
    risk_level: str | None
    description: str | None
    source_ref: str | None
    updated_at: datetime | None
    message: str


@router.get("/lookup", response_model=LookupOut)
def get_lookup(
    q: str = Query(..., min_length=1, max_length=300, description="STK, SĐT hoặc URL"),
    db: Session = Depends(get_db),
) -> LookupOut:
    try:
        result = lookup(db, q)
    except NormalizationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return LookupOut(**result.__dict__)
