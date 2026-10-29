from functools import lru_cache

from py_common.config import EmailServiceSettings, normalize_pem
from pydantic import Field, field_validator


class Settings(EmailServiceSettings):
    service_name: str = "auth"
    database_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth"

    jwt_private_key: str = Field(
        default="",
        description="PEM private key that signs access tokens; the public key is derived from it.",
    )
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # Transactional email ("password dimenticata"): fields in EmailServiceSettings.
    # First administrator created at startup when no administrator exists yet. For hosts
    # without a terminal (Render's free plan): remove the password once logged in.
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    initial_admin_name: str = "Amministratore"

    password_reset_minutes: int = 15

    # When false, events are only logged and lead consents are not consumed.
    events_enabled: bool = True
    events_queue: str = "auth.consents"

    @field_validator("initial_admin_email", "initial_admin_password", mode="after")
    @classmethod
    def _strip_initial_admin_credentials(cls, value: str) -> str:
        # Values pasted into a hosting dashboard often carry a trailing space or newline.
        return value.strip()

    @field_validator("initial_admin_name", mode="after")
    @classmethod
    def _default_initial_admin_name(cls, value: str) -> str:
        # A variable left empty on the host arrives as "", which would make the name invalid
        # and silently skip the creation of the administrator.
        return value.strip() or "Amministratore"

    @field_validator("jwt_private_key", mode="after")
    @classmethod
    def _normalize_private_key(cls, value: str) -> str:
        # Hosting dashboards often paste a multi-line key into a single-line field.
        return normalize_pem(value) if value else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
