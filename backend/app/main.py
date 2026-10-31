from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin_alerts, admin_contents, auth, contents, lookup
from app.core.config import get_settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Demo v1: tạo bảng tự động. Có thể thay bằng Alembic ở giai đoạn sau.
    from app.models import Alert, AuditLog, ContentItem, User  # noqa: F401  (đăng ký model)

    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(lookup.router)
app.include_router(admin_alerts.router)
app.include_router(contents.router)
app.include_router(admin_contents.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
