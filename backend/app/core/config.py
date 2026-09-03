from functools import lru_cache
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
