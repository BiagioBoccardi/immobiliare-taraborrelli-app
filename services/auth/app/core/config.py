from functools import lru_cache
from typing import Literal

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

    # Transactional email ("password dimenticata"). "outbox" saves the emails as files in
    # email_outbox_dir (local development); "smtp" sends them through any SMTP provider.
    email_backend: Literal["outbox", "smtp"] = "outbox"
    email_outbox_dir: str = "outbox"
    email_from: str = "Immobiliare Taraborrelli <noreply@immobiliaretaraborrelli.it>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False  # true for port 465; otherwise STARTTLS is used
    password_reset_minutes: int = 15

    # When false, events are only logged and lead consents are not consumed.
    events_enabled: bool = True
    events_queue: str = "auth.consents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
