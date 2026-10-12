from functools import lru_cache

from py_common.config import BaseServiceSettings
from pydantic import Field


class Settings(BaseServiceSettings):
    service_name: str = "auth"
    database_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth"

    jwt_private_key: str = Field(
        default="",
        description="PEM private key that signs access tokens; the public key is derived from it.",
    )
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # When false, events are only logged and lead consents are not consumed.
    events_enabled: bool = True
    events_queue: str = "auth.consents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
