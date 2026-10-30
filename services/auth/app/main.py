from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from py_common.config import describe_pem
from py_common.email import build_email_sender
from py_common.errors import register_error_handlers
from py_common.events import EventPublisher, RabbitMQConsumer, RabbitMQEventPublisher
from py_common.health import health_router
from py_common.logging import add_request_id_middleware, configure_logging
from py_common.ratelimit import RateLimiter
from py_common.security import TokenVerifier

from app.api import auth, me, users
from app.cli import ensure_initial_admin
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.core.security import AccessTokenIssuer, PasswordHasher, public_key_from_private
from app.events.consumers import LEAD_CONSENT_ROUTING_KEY, LeadConsentHandler
from app.events.publisher import LoggingEventPublisher

API_PREFIX = "/api/v1/auth"
# Requests per visitor per minute on login and similar routes, when rate limiting is on.
AUTH_PER_MINUTE = 20


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.service_name, settings.log_level)
    public_key = ""
    if settings.jwt_private_key:
        try:
            public_key = public_key_from_private(settings.jwt_private_key)
        except ValueError as error:
            # Says what is wrong with the pasted key without revealing it.
            raise RuntimeError(
                f"JWT_PRIVATE_KEY cannot be read: {describe_pem(settings.jwt_private_key)}"
            ) from error

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not settings.jwt_private_key:
            raise RuntimeError("JWT_PRIVATE_KEY is required by the auth service")
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        app.state.session_factory = session_factory
        if settings.initial_admin_email and settings.initial_admin_password:
            await ensure_initial_admin(
                session_factory,
                settings.initial_admin_email,
                settings.initial_admin_password,
                settings.initial_admin_name,
            )
        publisher: EventPublisher = LoggingEventPublisher()
        consumer: RabbitMQConsumer | None = None
        if settings.events_enabled:
            publisher = RabbitMQEventPublisher(settings.rabbitmq_url, settings.events_exchange)
            consumer = RabbitMQConsumer(
                settings.rabbitmq_url,
                settings.events_exchange,
                settings.events_queue,
                [LEAD_CONSENT_ROUTING_KEY],
                LeadConsentHandler(session_factory),
            )
            consumer.start_in_background()
        app.state.publisher = publisher
        try:
            yield
        finally:
            if consumer is not None:
                await consumer.stop()
            if isinstance(publisher, RabbitMQEventPublisher):
                await publisher.close()
            await engine.dispose()

    app = FastAPI(
        title="Auth service",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )
    app.state.settings = settings
    app.state.password_hasher = PasswordHasher()
    app.state.email_sender = build_email_sender(settings)
    app.state.auth_limiter = (
        RateLimiter(AUTH_PER_MINUTE, 60) if settings.rate_limit_enabled else None
    )
    app.state.token_issuer = AccessTokenIssuer(
        settings.jwt_private_key,
        settings.jwt_algorithm,
        settings.jwt_audience,
        settings.jwt_issuer,
        timedelta(minutes=settings.access_token_minutes),
    )
    # The auth service verifies its own tokens with the public key, like every other service.
    app.state.token_verifier = TokenVerifier(
        public_key,
        settings.jwt_algorithm,
        settings.jwt_audience,
        settings.jwt_issuer,
    )
    register_error_handlers(app)
    add_request_id_middleware(app)
    app.include_router(health_router())
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(me.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    return app


app = create_app()
