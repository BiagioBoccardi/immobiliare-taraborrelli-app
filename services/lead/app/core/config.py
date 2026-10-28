from functools import lru_cache
from typing import Annotated, Literal

from py_common.config import BaseServiceSettings
from pydantic import Field, field_validator
from pydantic_settings import NoDecode


class Settings(BaseServiceSettings):
    service_name: str = "lead"
    database_url: str = "postgresql+asyncpg://lead:lead@localhost:5432/lead"
    # How long after the first step an owner can still add optional details to a valuation.
    valuation_completion_window_days: int = 7
    # When false, events are only logged (useful to run the service without RabbitMQ).
    events_enabled: bool = True
    events_queue: str = "lead.user-deletions"

    # Notice to the agency for every new request. Empty list: no email is sent.
    # STAFF_NOTIFICATION_EMAILS is a comma-separated list of addresses.
    staff_notification_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Address of the admin panel, used for the link in the email (e.g. https://admin.example.it).
    admin_panel_url: str = ""
    # "outbox" saves the emails as files in email_outbox_dir (local development);
    # "smtp" sends them through any SMTP provider.
    email_backend: Literal["outbox", "smtp"] = "outbox"
    email_outbox_dir: str = "outbox"
    email_from: str = "Immobiliare Taraborrelli <noreply@immobiliaretaraborrelli.it>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False  # true for port 465; otherwise STARTTLS is used

    @field_validator("staff_notification_emails", mode="before")
    @classmethod
    def _split_emails(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
