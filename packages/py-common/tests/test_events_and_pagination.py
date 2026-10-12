import uuid

import pytest
from pydantic import ValidationError

from py_common.events import Event, InMemoryEventPublisher
from py_common.events.lead import ValuationRequestedV1
from py_common.pagination import Page, PageParams


def test_wrap_sets_type_version_and_routing_key() -> None:
    payload = ValuationRequestedV1(
        lead_id=uuid.uuid4(), priority="high", municipality="Chieti", property_type="apartment"
    )

    event = Event.wrap(payload, producer="lead")

    assert event.event_type == "lead.valuation_requested"
    assert event.version == 1
    assert event.routing_key == "lead.valuation_requested.v1"


def test_event_roundtrip_through_json_preserves_payload() -> None:
    payload = ValuationRequestedV1(
        lead_id=uuid.uuid4(), priority="low", municipality="Chieti", property_type="house"
    )
    event = Event.wrap(payload, producer="lead")

    parsed = Event[ValuationRequestedV1].model_validate_json(event.model_dump_json())

    assert parsed == event


def test_payload_with_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ValuationRequestedV1.model_validate(
            {
                "lead_id": str(uuid.uuid4()),
                "priority": "low",
                "municipality": "Chieti",
                "property_type": "house",
                "phone": "333",
            }
        )


async def test_in_memory_publisher_collects_events() -> None:
    publisher = InMemoryEventPublisher()
    payload = ValuationRequestedV1(
        lead_id=uuid.uuid4(), priority="medium", municipality="Chieti", property_type="villa"
    )

    await publisher.publish(Event.wrap(payload, producer="lead"))

    assert [e.event_type for e in publisher.events] == ["lead.valuation_requested"]


def test_page_params_offset_and_page_count() -> None:
    params = PageParams(page=3, size=10)
    page = Page[int](items=[1], total=21, page=3, size=10)

    assert params.offset == 20
    assert page.pages == 3
