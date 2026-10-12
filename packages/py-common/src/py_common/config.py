from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Settings shared by every service. Services subclass this to add their own fields."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "service"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="SQLAlchemy async URL of the database owned by this service.",
    )
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    events_exchange: str = "taraborrelli.events"

    jwt_public_key: str = Field(
        default="",
        description="PEM public key used to verify access tokens issued by the auth service.",
    )
    jwt_algorithm: str = "RS256"
    jwt_audience: str = "taraborrelli"
    jwt_issuer: str = "taraborrelli-auth"
