import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordReset


class PasswordResetRepository(Protocol):
    async def add(self, reset: PasswordReset) -> PasswordReset: ...

    async def latest_for_user(self, user_id: uuid.UUID) -> PasswordReset | None: ...

    async def close_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None: ...


class SqlPasswordResetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reset: PasswordReset) -> PasswordReset:
        self._session.add(reset)
        await self._session.flush()
        return reset

    async def latest_for_user(self, user_id: uuid.UUID) -> PasswordReset | None:
        # Locked, so two attempts at the same time cannot both pass the attempts limit.
        result = await self._session.scalars(
            select(PasswordReset)
            .where(PasswordReset.user_id == user_id)
            .order_by(PasswordReset.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        return result.first()

    async def close_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user_id, PasswordReset.used_at.is_(None))
            .values(used_at=now)
            .execution_options(synchronize_session="fetch")
        )
