from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from py_common.events import EventPublisher
from py_common.security import TokenVerifier, build_auth_dependencies
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.properties import SqlPropertyRepository
from app.services.properties import PropertyService
from app.storage.base import MediaStorage


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session


def get_publisher(request: Request) -> EventPublisher:
    return cast(EventPublisher, request.app.state.publisher)


def get_storage(request: Request) -> MediaStorage:
    return cast(MediaStorage, request.app.state.storage)


def get_token_verifier(request: Request) -> TokenVerifier:
    return cast(TokenVerifier, request.app.state.token_verifier)


def get_property_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_storage)],
    publisher: Annotated[EventPublisher, Depends(get_publisher)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> PropertyService:
    return PropertyService(
        SqlPropertyRepository(session),
        storage,
        publisher,
        max_photo_bytes=settings.max_photo_bytes,
        max_photos=settings.max_photos_per_property,
    )


require_user, require_staff = build_auth_dependencies(get_token_verifier)
