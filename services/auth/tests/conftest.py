from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from py_common.events import InMemoryEventPublisher
from py_common.security import Role
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.dependencies import get_publisher, get_session
from app.main import create_app
from app.models.user import User
from tests.factories import make_user

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_DIRS = ("integration", "api", "events")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Tests that need PostgreSQL are marked automatically from their folder.
    for item in items:
        if any(f"/tests/{d}/" in str(item.path) for d in CONTAINER_DIRS):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="session")
def make_token(private_key: str) -> Callable[..., str]:
    def _make(user: User, **overrides: Any) -> str:
        claims: dict[str, Any] = {
            "sub": str(user.id),
            "roles": [user.role.value],
            "aud": "taraborrelli",
            "iss": "taraborrelli-auth",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, private_key, algorithm="RS256")

    return _make


def run_migrations(database_url: str, revision: str = "head", downgrade: bool = False) -> None:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    if downgrade:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        # The schema is created by the migrations, so they are tested too.
        run_migrations(url)
        yield url


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Connection inside a transaction that is rolled back after each test."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    # Commits become savepoints, so the outer rollback still cleans everything.
    return async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def publisher() -> InMemoryEventPublisher:
    return InMemoryEventPublisher()


@pytest.fixture
def settings(private_key: str) -> Settings:
    return Settings(jwt_private_key=private_key, events_enabled=False, log_level="WARNING")


@pytest.fixture
def app(settings: Settings, db_session: AsyncSession, publisher: InMemoryEventPublisher) -> FastAPI:
    application = create_app(settings)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_publisher] = lambda: publisher
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _store_user(db_session: AsyncSession, **overrides: Any) -> User:
    user = make_user(**overrides)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    return await _store_user(db_session)


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    return await _store_user(db_session, role=Role.ADMIN, full_name="Admin Prova")


@pytest.fixture
async def staff(db_session: AsyncSession) -> User:
    return await _store_user(db_session, role=Role.STAFF, full_name="Staff Prova")


@pytest.fixture
def auth_headers(make_token: Callable[..., str]) -> Callable[[User], dict[str, str]]:
    def _headers(account: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(account)}"}

    return _headers
