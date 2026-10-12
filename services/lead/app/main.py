from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from py_common.errors import register_error_handlers
from py_common.events import EventPublisher, RabbitMQEventPublisher
from py_common.health import health_router
from py_common.logging import add_request_id_middleware, configure_logging
from py_common.security import TokenVerifier

from app.api import public, staff
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.events.publisher import LoggingEventPublisher

API_PREFIX = "/api/v1/lead"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        publisher: EventPublisher
        if settings.events_enabled:
            publisher = RabbitMQEventPublisher(settings.rabbitmq_url, settings.events_exchange)
        else:
            publisher = LoggingEventPublisher()
        app.state.session_factory = create_session_factory(engine)
        app.state.publisher = publisher
        try:
            yield
        finally:
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
    app.state.token_verifier = TokenVerifier(
        settings.jwt_public_key, settings.jwt_algorithm, settings.jwt_audience, settings.jwt_issuer
    )
    register_error_handlers(app)
    add_request_id_middleware(app)
    app.include_router(health_router())
    app.include_router(public.router, prefix=API_PREFIX)
    app.include_router(staff.router, prefix=API_PREFIX)
    return app


app = create_app()
