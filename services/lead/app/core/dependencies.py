from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, cast

from fastapi import Depends, Request
from py_common.events import EventPublisher
from py_common.security import (
    TokenVerifier,
    build_auth_dependencies,
    build_optional_user_dependency,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.lead import SqlLeadRepository
from app.services.lead import LeadService


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session


def get_publisher(request: Request) -> EventPublisher:
    return cast(EventPublisher, request.app.state.publisher)


def get_token_verifier(request: Request) -> TokenVerifier:
    return cast(TokenVerifier, request.app.state.token_verifier)


def get_lead_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    publisher: Annotated[EventPublisher, Depends(get_publisher)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> LeadService:
    return LeadService(
        SqlLeadRepository(session),
        publisher,
        completion_window=timedelta(days=settings.valuation_completion_window_days),
    )


require_user, require_staff = build_auth_dependencies(get_token_verifier)
optional_user = build_optional_user_dependency(get_token_verifier)
