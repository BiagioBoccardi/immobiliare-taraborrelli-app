from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from py_common.errors import register_error_handlers
from py_common.events import EventPublisher, RabbitMQEventPublisher
from py_common.health import health_router
from py_common.logging import add_request_id_middleware, configure_logging
from py_common.security import TokenVerifier

from app.api import admin, catalog
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.events.publisher import LoggingEventPublisher
from app.services.properties import PUBLIC_MEDIA_PREFIX
from app.storage.base import MediaStorage
from app.storage.cloudinary import CloudinaryCredentials, CloudinaryMediaStorage
from app.storage.s3 import S3MediaStorage

API_PREFIX = "/api/v1/property"


def build_storage(settings: Settings) -> MediaStorage:
    """Cloudinary when CLOUDINARY_URL is set (free hosting), S3-compatible otherwise."""
    if settings.cloudinary_url:
        return CloudinaryMediaStorage(CloudinaryCredentials.from_url(settings.cloudinary_url))
    return S3MediaStorage(
        settings.s3_endpoint_url,
        settings.s3_region,
        settings.s3_access_key,
        settings.s3_secret_key,
        settings.s3_bucket,
        settings.media_public_base_url,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        publisher: EventPublisher = LoggingEventPublisher()
        if settings.events_enabled:
            publisher = RabbitMQEventPublisher(settings.rabbitmq_url, settings.events_exchange)
        app.state.publisher = publisher
        if settings.s3_create_bucket and isinstance(storage, S3MediaStorage):
            await storage.ensure_public_bucket(PUBLIC_MEDIA_PREFIX)
        try:
            yield
        finally:
            if isinstance(publisher, RabbitMQEventPublisher):
                await publisher.close()
            await engine.dispose()

    app = FastAPI(
        title="Property service",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )
    app.state.settings = settings
    storage = build_storage(settings)
    app.state.storage = storage
    app.state.token_verifier = TokenVerifier(
        settings.jwt_public_key, settings.jwt_algorithm, settings.jwt_audience, settings.jwt_issuer
    )
    register_error_handlers(app)
    add_request_id_middleware(app)
    app.include_router(health_router())
    app.include_router(catalog.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    return app


app = create_app()
