from py_common.events import Event
from py_common.events.lead import ValuationRequestedV1
from sqlalchemy import text

from app.core.config import Settings
from app.events.publisher import LoggingEventPublisher
from app.main import create_app


async def test_lifespan_with_events_disabled_sets_up_state(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url, events_enabled=False))

    async with app.router.lifespan_context(app):
        publisher = app.state.publisher
        factory = app.state.session_factory
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))

    assert isinstance(publisher, LoggingEventPublisher)
    assert result.scalar_one() == 1


async def test_logging_publisher_accepts_event() -> None:
    publisher = LoggingEventPublisher()
    payload = ValuationRequestedV1.model_validate(
        {
            "lead_id": "00000000-0000-0000-0000-000000000001",
            "priority": "low",
            "municipality": "Chieti",
            "property_type": "house",
        }
    )

    await publisher.publish(Event.wrap(payload, producer="lead"))
