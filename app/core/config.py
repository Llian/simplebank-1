from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "insecure-development-secret-change-me"  # noqa: S105  # nosec B105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./simplebank.db"
    enable_test_endpoints: bool = False
    jwt_secret_key: str = _DEV_JWT_SECRET
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_hours: int = 24

    def model_post_init(self, __context: Any) -> None:
        if self.enable_test_endpoints and self.environment == "production":
            raise RuntimeError("enable_test_endpoints must not be set when environment=production")
        if self.environment == "production" and self.jwt_secret_key == _DEV_JWT_SECRET:
            raise RuntimeError("jwt_secret_key must be set when environment=production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
