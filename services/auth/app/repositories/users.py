import uuid
from typing import Protocol

from py_common.security import Role
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository(Protocol):
    async def add(self, user: User) -> User: ...

    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def list(self, role: Role | None, offset: int, limit: int) -> tuple[list[User], int]: ...

    async def count_active_admins(self) -> int: ...

    async def delete(self, user: User) -> None: ...


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.scalars(select(User).where(User.email == email.lower()))
        return result.first()

    async def list(self, role: Role | None, offset: int, limit: int) -> tuple[list[User], int]:
        query = select(User)
        if role is not None:
            query = query.where(User.role == role)
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._session.scalars(
            query.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)
        )
        return list(rows), int(total or 0)

    async def count_active_admins(self) -> int:
        total = await self._session.scalar(
            select(func.count()).where(User.role == Role.ADMIN, User.is_active.is_(True))
        )
        return int(total or 0)

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()
