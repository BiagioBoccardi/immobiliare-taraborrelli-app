import uuid
from collections.abc import AsyncIterator

import pytest
from py_common.events import Event
from py_common.events.auth import UserDeletedV1
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.events.consumers import UserDeletedHandler
from app.models.lead import Lead
from tests.factories import make_lead


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions sharing one connection whose transaction is rolled back after the test."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        yield async_sessionmaker(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        await transaction.rollback()


async def _count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(Lead)) or 0)


async def test_user_deleted_event_removes_linked_requests_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add_all([make_lead(user_id=user_id), make_lead(user_id=user_id), make_lead()])
        await session.commit()
    handler = UserDeletedHandler(session_factory)
    body = Event.wrap(UserDeletedV1(user_id=user_id), producer="auth").model_dump_json().encode()
    await handler("auth.user_deleted.v1", body)

    await handler("auth.user_deleted.v1", body)

    assert await _count(session_factory) == 1
