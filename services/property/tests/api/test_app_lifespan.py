from py_common.events import Event
from py_common.events.property import PropertyUnpublishedV1
from sqlalchemy import text

from app.core.config import Settings
from app.events.publisher import LoggingEventPublisher
from app.main import create_app
from app.storage.s3 import S3MediaStorage


async def test_lifespan_with_events_disabled_sets_up_state(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url, events_enabled=False))

    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as session:
            result = await session.execute(text("SELECT 1"))
        publisher = app.state.publisher

    assert isinstance(publisher, LoggingEventPublisher)
    assert result.scalar_one() == 1


def test_s3_storage_builds_public_url_without_double_slash() -> None:
    storage = S3MediaStorage("http://minio:9000", "us-east-1", "k", "s", "b", "https://cdn.test/")

    url = storage.public_url("properties/1/a.jpg")

    assert url == "https://cdn.test/properties/1/a.jpg"


async def test_logging_publisher_accepts_event() -> None:
    payload = PropertyUnpublishedV1.model_validate(
        {"property_id": "00000000-0000-0000-0000-000000000001", "status": "sold"}
    )

    await LoggingEventPublisher().publish(Event.wrap(payload, producer="property"))
