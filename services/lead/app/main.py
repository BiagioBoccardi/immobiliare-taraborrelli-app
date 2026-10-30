from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from py_common.email import build_email_sender
from py_common.errors import register_error_handlers
from py_common.events import EventPublisher, RabbitMQConsumer, RabbitMQEventPublisher
from py_common.health import health_router
from py_common.logging import add_request_id_middleware, configure_logging
from py_common.ratelimit import RateLimiter
from py_common.security import TokenVerifier

from app.api import omi, public, staff
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.events.consumers import USER_DELETED_ROUTING_KEY, UserDeletedHandler
from app.events.publisher import LoggingEventPublisher
from app.services.geocoding import NominatimGeocoder
from app.services.notifications import EmailStaffNotifier, NoStaffNotifier, StaffNotifier

API_PREFIX = "/api/v1/lead"
# Requests per visitor per minute on the public forms, when rate limiting is on.
FORMS_PER_MINUTE = 10


def build_staff_notifier(settings: Settings) -> StaffNotifier:
    if not settings.staff_notification_emails:
        return NoStaffNotifier()
    return EmailStaffNotifier(
        build_email_sender(settings),
        settings.staff_notification_emails,
        settings.admin_panel_url,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        publisher: EventPublisher = LoggingEventPublisher()
        consumer: RabbitMQConsumer | None = None
        if settings.events_enabled:
            publisher = RabbitMQEventPublisher(settings.rabbitmq_url, settings.events_exchange)
            consumer = RabbitMQConsumer(
                settings.rabbitmq_url,
                settings.events_exchange,
                settings.events_queue,
                [USER_DELETED_ROUTING_KEY],
                UserDeletedHandler(session_factory),
            )
            consumer.start_in_background()
        app.state.session_factory = session_factory
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
        title="Lead service",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )
    app.state.settings = settings
    app.state.staff_notifier = build_staff_notifier(settings)
    app.state.forms_limiter = (
        RateLimiter(FORMS_PER_MINUTE, 60) if settings.rate_limit_enabled else None
    )
    app.state.token_verifier = TokenVerifier(
        settings.jwt_public_key, settings.jwt_algorithm, settings.jwt_audience, settings.jwt_issuer
    )
    app.state.geocoder = NominatimGeocoder(
        settings.geocoder_url,
        settings.geocoder_user_agent,
        email=settings.geocoder_email,
        viewbox=settings.geocoder_viewbox,
    )
    register_error_handlers(app)
    add_request_id_middleware(app)
    app.include_router(health_router())
    app.include_router(public.router, prefix=API_PREFIX)
    app.include_router(staff.router, prefix=API_PREFIX)
    app.include_router(omi.router, prefix=API_PREFIX)
    return app


app = create_app()
