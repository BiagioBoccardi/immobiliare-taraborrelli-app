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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import Settings
from app.core.dependencies import get_listing_prices, get_publisher, get_session
from app.main import create_app
from tests.unit.fakes import FakeListingPrices

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_DIRS = ("integration", "api", "events")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Tests that need PostgreSQL are marked automatically from their folder.
    for item in items:
        if any(f"/tests/{d}/" in str(item.path) for d in CONTAINER_DIRS):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def rsa_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def make_token(rsa_keys: tuple[str, str]) -> Callable[..., str]:
    def _make(roles: list[str], **overrides: Any) -> str:
        claims: dict[str, Any] = {
            "sub": "staff-1",
            "roles": roles,
            "aud": "taraborrelli",
            "iss": "taraborrelli-auth",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, rsa_keys[0], algorithm="RS256")

    return _make


@pytest.fixture
def staff_headers(make_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(['staff'])}"}


@pytest.fixture
def user_headers(make_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(['user'])}"}


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
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session inside a transaction that is rolled back after each test."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
def publisher() -> InMemoryEventPublisher:
    return InMemoryEventPublisher()


@pytest.fixture
def settings(rsa_keys: tuple[str, str]) -> Settings:
    return Settings(jwt_public_key=rsa_keys[1], events_enabled=False, log_level="WARNING")


@pytest.fixture
def app(settings: Settings, db_session: AsyncSession, publisher: InMemoryEventPublisher) -> FastAPI:
    application = create_app(settings)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_publisher] = lambda: publisher
    # The property service is never called: no agency listing unless a test sets one.
    application.dependency_overrides[get_listing_prices] = lambda: FakeListingPrices()
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
