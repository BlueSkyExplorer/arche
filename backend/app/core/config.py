from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://postgres@localhost:5432/arche_dev",
        validation_alias="DATABASE_URL",
    )
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    auth_mode: Literal["stub"] = Field(default="stub", validation_alias="AUTH_MODE")
    stub_auth_email: str = Field(default="demo@example.com", validation_alias="STUB_AUTH_EMAIL")
    storage_local_dir: Path = Field(default=Path(".storage"), validation_alias="STORAGE_LOCAL_DIR")
    libreoffice_bin: str = Field(
        default="/Applications/LibreOffice.app/Contents/MacOS/soffice",
        validation_alias="LIBREOFFICE_BIN",
    )
    export_max_pdf_timeout_s: int = Field(
        default=120, ge=1, validation_alias="EXPORT_MAX_PDF_TIMEOUT_S"
    )
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:3000"],
        validation_alias="CORS_ALLOW_ORIGINS",
    )
    ai_enabled: bool = Field(default=False, validation_alias="AI_ENABLED")
    ai_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="AI_BASE_URL"
    )
    ai_api_key: str = Field(default="", validation_alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", validation_alias="AI_MODEL")
    ai_timeout_s: int = Field(default=60, ge=1, validation_alias="AI_TIMEOUT_S")


@lru_cache
def get_settings() -> Settings:
    return Settings()
