import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, cast

from fastapi import Depends, Request
from py_common.errors import ForbiddenError
from py_common.events import EventPublisher
from py_common.security import Principal, Role, TokenVerifier, build_auth_dependencies
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import AccessTokenIssuer, PasswordHasher
from app.repositories.unit_of_work import SqlUnitOfWork
from app.services.auth import AuthService
from app.services.consents import ConsentService
from app.services.users import UserAdminService


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session


def get_unit_of_work(session: Annotated[AsyncSession, Depends(get_session)]) -> SqlUnitOfWork:
    return SqlUnitOfWork(session)


def get_publisher(request: Request) -> EventPublisher:
    return cast(EventPublisher, request.app.state.publisher)


def get_token_verifier(request: Request) -> TokenVerifier:
    return cast(TokenVerifier, request.app.state.token_verifier)


def get_token_issuer(request: Request) -> AccessTokenIssuer:
    return cast(AccessTokenIssuer, request.app.state.token_issuer)


def get_password_hasher(request: Request) -> PasswordHasher:
    return cast(PasswordHasher, request.app.state.password_hasher)


UoW = Annotated[SqlUnitOfWork, Depends(get_unit_of_work)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_auth_service(
    uow: UoW,
    hasher: Hasher,
    issuer: Annotated[AccessTokenIssuer, Depends(get_token_issuer)],
    publisher: Annotated[EventPublisher, Depends(get_publisher)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AuthService:
    return AuthService(uow, hasher, issuer, publisher, timedelta(days=settings.refresh_token_days))


def get_consent_service(uow: UoW) -> ConsentService:
    return ConsentService(uow)


def get_user_admin_service(uow: UoW, hasher: Hasher) -> UserAdminService:
    return UserAdminService(uow, hasher)


require_user, require_staff = build_auth_dependencies(get_token_verifier)


async def require_admin(principal: Annotated[Principal, Depends(require_user)]) -> Principal:
    if Role.ADMIN not in principal.roles:
        raise ForbiddenError("Administrator role required")
    return principal


def current_user_id(principal: Annotated[Principal, Depends(require_user)]) -> uuid.UUID:
    return uuid.UUID(principal.subject)
