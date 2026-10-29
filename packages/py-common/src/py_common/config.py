from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SSL_MODES_REQUIRING_TLS = {"require", "verify-ca", "verify-full"}


def normalize_database_url(url: str) -> str:
    """Turns a PostgreSQL address as given by hosting providers (Neon, Render, ...) into the
    form SQLAlchemy's async driver expects, so it can be pasted as it is:

    - postgres:// or postgresql:// becomes postgresql+asyncpg://
    - sslmode=require (libpq) becomes ssl=require (asyncpg); libpq-only options are dropped
    - Neon's pooled host (-pooler) becomes the direct host: the transaction pooler does not
      work with asyncpg's prepared statements
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+asyncpg"
    if scheme != "postgresql+asyncpg":
        return url
    netloc = parts.netloc.replace("-pooler.", ".", 1)
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            if value in _SSL_MODES_REQUIRING_TLS:
                query.append(("ssl", "require"))
        elif key in {"channel_binding", "options", "target_session_attrs"}:
            continue
        else:
            query.append((key, value))
    return urlunsplit((scheme, netloc, parts.path, urlencode(query), parts.fragment))


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

    # Rate limiting inside the service, for hosts without the Traefik gateway (Render).
    # Off by default: with docker compose the gateway already limits the requests.
    rate_limit_enabled: bool = False

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


class EmailServiceSettings(BaseServiceSettings):
    """Settings of the services that send email (see py_common.email)."""

    # "outbox" saves the emails as files in email_outbox_dir (local development); "smtp"
    # sends them through any SMTP provider; "brevo" uses Brevo's HTTPS API; "gmail_script"
    # sends from a Gmail account through a Google Apps Script web app
    # (infra/email/gmail-sender.gs). The last two work on hosts that block outgoing SMTP,
    # such as Render's free plan.
    email_backend: Literal["outbox", "smtp", "brevo", "gmail_script"] = "outbox"
    email_outbox_dir: str = "outbox"
    email_from: str = "Immobiliare Taraborrelli <noreply@immobiliaretaraborrelli.it>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False  # true for port 465; otherwise STARTTLS is used
    brevo_api_key: str = ""
    # Address of the Apps Script web app (https://script.google.com/macros/s/.../exec) and the
    # shared secret written in the script.
    gmail_script_url: str = ""
    gmail_script_token: str = ""
