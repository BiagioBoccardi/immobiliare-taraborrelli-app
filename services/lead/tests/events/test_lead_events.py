from httpx import AsyncClient
from py_common.events import Event, InMemoryEventPublisher
from py_common.events.lead import OwnerRequestReceivedV1, ValuationRequestedV1

from tests.factories import owner_request_payload, valuation_payload

BASE = "/api/v1/lead"


async def test_valuation_request_emits_schema_valid_event(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    response = await client.post(f"{BASE}/valuations", json=valuation_payload(intention="decided"))

    [event] = publisher.events
    parsed = Event[ValuationRequestedV1].model_validate_json(event.model_dump_json())
    assert parsed.routing_key == "lead.valuation_requested.v1"
    assert str(parsed.payload.lead_id) == response.json()["id"]
    assert parsed.payload.priority == "high"
    assert parsed.producer == "lead"


async def test_owner_request_emits_schema_valid_event_without_contacts(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    await client.post(f"{BASE}/owner-requests", json=owner_request_payload(kind="sell"))

    [event] = publisher.events
    parsed = Event[OwnerRequestReceivedV1].model_validate_json(event.model_dump_json())
    assert parsed.payload.kind == "sell"
    assert "Anna" not in event.model_dump_json()
    assert "3331112222" not in event.model_dump_json()


async def test_invalid_request_emits_no_event(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    await client.post(f"{BASE}/valuations", json=valuation_payload(rooms=0))

    assert publisher.events == []
