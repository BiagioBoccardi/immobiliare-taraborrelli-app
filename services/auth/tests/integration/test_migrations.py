import asyncio
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.models import Base
from tests.conftest import run_migrations


async def _table_names(url: str) -> list[str]:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: inspect(c).get_table_names())
    await engine.dispose()
    return sorted(names)


async def test_migrations_downgrade_and_upgrade_cleanly(
    engine: AsyncEngine, database_url: str
) -> None:
    async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
        await connection.exec_driver_sql("DROP DATABASE IF EXISTS migrations_check")
        await connection.exec_driver_sql("CREATE DATABASE migrations_check")
    url = (
        make_url(database_url)
        .set(database="migrations_check")
        .render_as_string(hide_password=False)
    )

    # Alembic's env.py runs its own event loop, so it is executed in a worker thread.
    await asyncio.to_thread(run_migrations, url)
    await asyncio.to_thread(run_migrations, url, "base", True)
    after_downgrade = await _table_names(url)
    await asyncio.to_thread(run_migrations, url)

    assert after_downgrade == ["alembic_version"]
    assert await _table_names(url) == [
        "alembic_version",
        "consent_records",
        "password_resets",
        "refresh_tokens",
        "users",
    ]


def _schema_diff(connection: Connection) -> list[Any]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def test_migrations_match_models(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        diff = await connection.run_sync(_schema_diff)

    assert diff == []
