import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app import cli
from app.core.config import Settings
from app.core.database import create_session_factory
from tests.conftest import run_migrations

PASSWORD = "Password-admin-1"


async def _create_database(server_url: str, name: str) -> None:
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {name}")
        await connection.exec_driver_sql(f"CREATE DATABASE {name}")
    await engine.dispose()


@pytest.fixture
def cli_database(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    # The CLI commits for real, so it runs on its own database.
    asyncio.run(_create_database(database_url, "cli_check"))
    url = make_url(database_url).set(database="cli_check").render_as_string(hide_password=False)
    run_migrations(url)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(database_url=url))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: PASSWORD)
    yield url


def test_create_admin_first_time_returns_0(cli_database: str) -> None:
    code = cli.main(["create-admin", "--email", "admin@example.com", "--name", "Admin Uno"])

    assert code == 0


def test_create_admin_when_admin_exists_returns_1(cli_database: str) -> None:
    cli.main(["create-admin", "--email", "admin@example.com", "--name", "Admin Uno"])

    code = cli.main(["create-admin", "--email", "altro@example.com", "--name", "Admin Due"])

    assert code == 1


def test_create_admin_with_invalid_email_returns_2(cli_database: str) -> None:
    code = cli.main(["create-admin", "--email", "non-valida", "--name", "Admin Uno"])

    assert code == 2


async def _count_admins(url: str) -> int:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        result = await connection.exec_driver_sql("SELECT count(*) FROM users WHERE role = 'admin'")
        count = int(result.scalar_one())
    await engine.dispose()
    return count


def _ensure(url: str, email: str, password: str) -> bool:
    async def run() -> bool:
        engine = create_async_engine(url)
        try:
            return await cli.ensure_initial_admin(
                create_session_factory(engine), email, password, "Admin Avvio"
            )
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_ensure_initial_admin_creates_it_only_once(cli_database: str) -> None:
    first = _ensure(cli_database, "avvio@example.com", PASSWORD)
    second = _ensure(cli_database, "altro@example.com", PASSWORD)

    assert (first, second) == (True, False)
    assert asyncio.run(_count_admins(cli_database)) == 1


def test_ensure_initial_admin_with_short_password_creates_nothing(cli_database: str) -> None:
    created = _ensure(cli_database, "avvio@example.com", "corta")

    assert created is False
    assert asyncio.run(_count_admins(cli_database)) == 0
