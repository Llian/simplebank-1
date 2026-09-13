from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./simplebank.db"
    enable_test_endpoints: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.enable_test_endpoints and self.environment == "production":
            raise RuntimeError("enable_test_endpoints must not be set when environment=production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
