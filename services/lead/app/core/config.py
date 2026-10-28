from functools import lru_cache
from typing import Annotated

from py_common.config import EmailServiceSettings
from pydantic import Field, field_validator
from pydantic_settings import NoDecode


class Settings(EmailServiceSettings):
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
    # Email backend and sender: fields in EmailServiceSettings.

    @field_validator("staff_notification_emails", mode="before")
    @classmethod
    def _split_emails(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
