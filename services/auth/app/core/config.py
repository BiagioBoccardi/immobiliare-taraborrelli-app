from functools import lru_cache

from py_common.config import EmailServiceSettings
from pydantic import Field


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
