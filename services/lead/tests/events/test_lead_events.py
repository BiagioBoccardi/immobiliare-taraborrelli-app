from httpx import AsyncClient
from py_common.events import Event, InMemoryEventPublisher
from py_common.events.lead import (
    CallbackRequestedV1,
    LeadConsentGivenV1,
    OwnerRequestReceivedV1,
    ValuationRequestedV1,
)

from tests.factories import callback_request_payload, owner_request_payload, valuation_payload

BASE = "/api/v1/lead"


async def test_valuation_request_emits_schema_valid_event(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    response = await client.post(f"{BASE}/valuations", json=valuation_payload(intention="decided"))

    event = publisher.events[0]
    parsed = Event[ValuationRequestedV1].model_validate_json(event.model_dump_json())
    assert parsed.routing_key == "lead.valuation_requested.v1"
    assert str(parsed.payload.lead_id) == response.json()["id"]
    assert parsed.payload.priority == "high"
    assert parsed.producer == "lead"


async def test_owner_request_emits_schema_valid_event_without_contacts(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    await client.post(f"{BASE}/owner-requests", json=owner_request_payload(kind="sell"))

    parsed = Event[OwnerRequestReceivedV1].model_validate_json(
        publisher.events[0].model_dump_json()
    )
    assert parsed.payload.kind == "sell"
    for event in publisher.events:
        assert "Anna" not in event.model_dump_json()
        assert "3331112222" not in event.model_dump_json()


async def test_invalid_request_emits_no_event(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    await client.post(f"{BASE}/valuations", json=valuation_payload(rooms=0))

    assert publisher.events == []


async def test_owner_request_emits_schema_valid_consent_event(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    response = await client.post(f"{BASE}/owner-requests", json=owner_request_payload())

    parsed = Event[LeadConsentGivenV1].model_validate_json(publisher.events[-1].model_dump_json())
    assert parsed.routing_key == "lead.consent_given.v1"
    assert str(parsed.payload.lead_id) == response.json()["id"]
    assert parsed.payload.purposes == ("contact",)


async def test_callback_request_emits_schema_valid_events_without_contacts(
    client: AsyncClient, publisher: InMemoryEventPublisher
) -> None:
    response = await client.post(
        f"{BASE}/callback-requests", json=callback_request_payload(preferred_time="evening")
    )

    parsed = Event[CallbackRequestedV1].model_validate_json(publisher.events[0].model_dump_json())
    consent = Event[LeadConsentGivenV1].model_validate_json(publisher.events[1].model_dump_json())
    assert parsed.routing_key == "lead.callback_requested.v1"
    assert str(parsed.payload.lead_id) == response.json()["id"]
    assert parsed.payload.preferred_time == "evening"
    assert consent.payload.purposes == ("contact",)
    for event in publisher.events:
        assert "Neri" not in event.model_dump_json()
        assert "luca.neri" not in event.model_dump_json()
        assert "3334445555" not in event.model_dump_json()
