from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình ứng dụng, đọc từ biến môi trường hoặc file .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Scam Shield VN"
    database_url: str = "sqlite:///./scam_shield.db"
    secret_key: str = "dev-only-change-me"
    fernet_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_attachments_per_tip: int = 3
    audit_retention_days: int = 365
    tip_rate_per_hour: int = 5          # số tố giác tối đa mỗi IP (đã băm) trong 1 giờ
    status_lookup_limit: int = 30       # số lần tra cứu mã theo dõi trong 5 phút mỗi IP


@lru_cache
def get_settings() -> Settings:
    return Settings()
