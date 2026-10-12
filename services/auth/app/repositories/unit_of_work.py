from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.consents import ConsentRepository, SqlConsentRepository
from app.repositories.refresh_tokens import RefreshTokenRepository, SqlRefreshTokenRepository
from app.repositories.users import SqlUserRepository, UserRepository


class UnitOfWork(Protocol):
    users: UserRepository
    refresh_tokens: RefreshTokenRepository
    consents: ConsentRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class SqlUnitOfWork:
    """Groups the repositories of one request so they commit in a single transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users: UserRepository = SqlUserRepository(session)
        self.refresh_tokens: RefreshTokenRepository = SqlRefreshTokenRepository(session)
        self.consents: ConsentRepository = SqlConsentRepository(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
