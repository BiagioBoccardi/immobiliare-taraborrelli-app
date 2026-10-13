from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from py_common.events import Event, InMemoryEventPublisher
from py_common.events.property import (
    PropertyPriceChangedV1,
    PropertyPublishedV1,
    PropertyUnpublishedV1,
)

from app.models.enums import PropertyStatus
from app.models.property import Property

Store = Callable[..., Awaitable[Property]]
BASE = "/api/v1/property/admin/properties"


async def test_publishing_emits_schema_valid_published_event(
    client: AsyncClient,
    store: Store,
    staff_headers: dict[str, str],
    publisher: InMemoryEventPublisher,
) -> None:
    item = await store(status=PropertyStatus.DRAFT, features=["garden"])

    await client.post(
        f"{BASE}/{item.id}/status", json={"status": "published"}, headers=staff_headers
    )

    [event] = publisher.events
    parsed = Event[PropertyPublishedV1].model_validate_json(event.model_dump_json())
    assert parsed.routing_key == "property.published.v1"
    assert parsed.payload.property_id == item.id
    assert parsed.payload.features == ("garden",)
    assert "Via di Prova" not in event.model_dump_json()


async def test_price_drop_emits_schema_valid_price_changed_event(
    client: AsyncClient,
    store: Store,
    staff_headers: dict[str, str],
    publisher: InMemoryEventPublisher,
) -> None:
    item = await store(price=200_000)

    await client.patch(f"{BASE}/{item.id}", json={"price": 185_000}, headers=staff_headers)

    [event] = publisher.events
    parsed = Event[PropertyPriceChangedV1].model_validate_json(event.model_dump_json())
    assert (parsed.payload.old_price, parsed.payload.new_price) == (200_000, 185_000)


async def test_renting_emits_schema_valid_unpublished_event(
    client: AsyncClient,
    store: Store,
    staff_headers: dict[str, str],
    publisher: InMemoryEventPublisher,
) -> None:
    item = await store(contract="rent")

    await client.post(f"{BASE}/{item.id}/status", json={"status": "rented"}, headers=staff_headers)

    [event] = publisher.events
    parsed = Event[PropertyUnpublishedV1].model_validate_json(event.model_dump_json())
    assert parsed.payload.status == "rented"


async def test_editing_description_emits_no_event(
    client: AsyncClient,
    store: Store,
    staff_headers: dict[str, str],
    publisher: InMemoryEventPublisher,
) -> None:
    item = await store()

    await client.patch(
        f"{BASE}/{item.id}", json={"description": "Nuova descrizione"}, headers=staff_headers
    )

    assert publisher.events == []
