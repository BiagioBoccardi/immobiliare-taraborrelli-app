import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.events.publisher import LoggingEventPublisher
from app.main import create_app


async def test_lifespan_with_events_disabled_sets_up_state(
    database_url: str, private_key: str
) -> None:
    app = create_app(
        Settings(database_url=database_url, jwt_private_key=private_key, events_enabled=False)
    )

    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as session:
            result = await session.execute(text("SELECT 1"))
        publisher = app.state.publisher

    assert isinstance(publisher, LoggingEventPublisher)
    assert result.scalar_one() == 1


async def test_lifespan_without_private_key_refuses_to_start(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url, jwt_private_key="", events_enabled=False))

    with pytest.raises(RuntimeError):
        async with app.router.lifespan_context(app):
            pass
