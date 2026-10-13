from collections.abc import AsyncIterator, Iterator
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
from app.core.dependencies import get_publisher, get_session, get_storage
from app.main import create_app
from app.models.property import Property
from tests.factories import make_property
from tests.unit.fakes import InMemoryStorage

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


def _token(private_key: str, roles: list[str]) -> str:
    claims: dict[str, Any] = {
        "sub": "account-1",
        "roles": roles,
        "aud": "taraborrelli",
        "iss": "taraborrelli-auth",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


@pytest.fixture
def staff_headers(rsa_keys: tuple[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(rsa_keys[0], ['staff'])}"}


@pytest.fixture
def user_headers(rsa_keys: tuple[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(rsa_keys[0], ['user'])}"}


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
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def settings(rsa_keys: tuple[str, str]) -> Settings:
    return Settings(
        jwt_public_key=rsa_keys[1],
        events_enabled=False,
        log_level="WARNING",
        max_photo_bytes=1024,
        max_photos_per_property=3,
    )


@pytest.fixture
def app(
    settings: Settings,
    db_session: AsyncSession,
    publisher: InMemoryEventPublisher,
    storage: InMemoryStorage,
) -> FastAPI:
    application = create_app(settings)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_publisher] = lambda: publisher
    application.dependency_overrides[get_storage] = lambda: storage
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def store(db_session: AsyncSession) -> Any:
    """Saves a property built by the factory (without the `number`, assigned by PostgreSQL)."""

    async def _store(photos: int = 1, **overrides: Any) -> Property:
        item = make_property(photos=photos, **overrides)
        del item.number
        db_session.add(item)
        await db_session.flush()
        await db_session.refresh(item, attribute_names=["number"])
        return item

    return _store
