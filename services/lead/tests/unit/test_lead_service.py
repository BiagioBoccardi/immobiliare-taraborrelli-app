import uuid
from datetime import UTC, datetime, timedelta

import pytest
from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import InMemoryEventPublisher
from py_common.pagination import PageParams

from app.models.enums import LeadKind, LeadPriority, LeadStatus
from app.schemas.lead import (
    CallbackRequestCreate,
    LeadFilters,
    LeadUpdate,
    OwnerRequestCreate,
    ValuationCreate,
    ValuationDetails,
)
from app.services.lead import LeadService
from app.services.tokens import token_matches
from tests.factories import (
    callback_request_payload,
    consent_payload,
    make_lead,
    owner_request_payload,
    valuation_payload,
)
from tests.unit.fakes import (
    FailingNotifier,
    FailingPublisher,
    FakeLeadRepository,
    RecordingNotifier,
)

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
WINDOW = timedelta(days=7)


def build_service(
    repo: FakeLeadRepository | None = None,
    publisher: InMemoryEventPublisher | FailingPublisher | None = None,
    now: datetime = NOW,
) -> tuple[LeadService, FakeLeadRepository, InMemoryEventPublisher | FailingPublisher]:
    repo = repo or FakeLeadRepository()
    publisher = publisher or InMemoryEventPublisher()
    return LeadService(repo, publisher, WINDOW, clock=lambda: now), repo, publisher


async def test_create_valuation_stores_lead_with_priority_from_intention() -> None:
    service, repo, _ = build_service()

    created = await service.create_valuation(
        ValuationCreate.model_validate(valuation_payload(intention="decided"))
    )

    stored = repo.leads[created.lead.id]
    assert stored.kind is LeadKind.VALUATION
    assert stored.status is LeadStatus.NEW
    assert stored.priority is LeadPriority.HIGH
    assert stored.contact_consent_at == NOW
    assert repo.commits == 1


async def test_create_valuation_returns_token_stored_only_as_hash() -> None:
    service, repo, _ = build_service()

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    stored_hash = repo.leads[created.lead.id].completion_token_hash
    assert stored_hash != created.completion_token
    assert token_matches(created.completion_token, stored_hash)
    assert created.completion_expires_at == NOW + WINDOW


async def test_create_valuation_emits_event_without_personal_data() -> None:
    service, _, publisher = build_service()

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert isinstance(publisher, InMemoryEventPublisher)
    event, consent_event = publisher.events
    assert event.event_type == "lead.valuation_requested"
    assert event.payload.lead_id == created.lead.id
    assert consent_event.event_type == "lead.consent_given"
    for emitted in publisher.events:
        dumped = emitted.model_dump_json()
        assert "Mario" not in dumped
        assert "3330000000" not in dumped


async def test_create_valuation_when_broker_fails_still_stores_lead() -> None:
    service, repo, _ = build_service(publisher=FailingPublisher())

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert created.lead.id in repo.leads


async def test_complete_valuation_with_valid_token_merges_details() -> None:
    lead = make_lead(token="secret", created_at=NOW, details={"floor": 1})
    service, _, _ = build_service(FakeLeadRepository([lead]))

    await service.complete_valuation(
        lead.id, "secret", ValuationDetails(bathrooms=2, email="mario@example.com")
    )

    assert lead.details == {"floor": 1, "bathrooms": 2, "expected_price_unknown": False}
    assert lead.email == "mario@example.com"


async def test_complete_valuation_with_wrong_token_raises_not_found() -> None:
    lead = make_lead(token="secret", created_at=NOW)
    service, _, _ = build_service(FakeLeadRepository([lead]))

    with pytest.raises(NotFoundError):
        await service.complete_valuation(lead.id, "guess", ValuationDetails())


async def test_complete_valuation_of_unknown_lead_raises_not_found() -> None:
    service, _, _ = build_service()

    with pytest.raises(NotFoundError):
        await service.complete_valuation(uuid.uuid4(), "secret", ValuationDetails())


async def test_complete_valuation_after_window_raises_conflict() -> None:
    lead = make_lead(token="secret", created_at=NOW - WINDOW - timedelta(minutes=1))
    service, _, _ = build_service(FakeLeadRepository([lead]))

    with pytest.raises(ConflictError) as exc_info:
        await service.complete_valuation(lead.id, "secret", ValuationDetails())

    assert exc_info.value.code == "completion_window_expired"


async def test_complete_valuation_on_owner_request_raises_not_found() -> None:
    lead = make_lead(token="secret", created_at=NOW, kind=LeadKind.SELL)
    service, _, _ = build_service(FakeLeadRepository([lead]))

    with pytest.raises(NotFoundError):
        await service.complete_valuation(lead.id, "secret", ValuationDetails())


@pytest.mark.parametrize("kind", ["sell", "rent"])
async def test_create_owner_request_emits_event_with_kind(kind: str) -> None:
    service, repo, publisher = build_service()

    lead = await service.create_owner_request(
        OwnerRequestCreate.model_validate(owner_request_payload(kind=kind))
    )

    assert isinstance(publisher, InMemoryEventPublisher)
    event = publisher.events[0]
    assert event.event_type == "lead.owner_request_received"
    assert event.payload.kind == kind
    assert repo.leads[lead.id].completion_token_hash is None


async def test_update_lead_changes_only_sent_fields() -> None:
    lead = make_lead(staff_notes="old")
    service, _, _ = build_service(FakeLeadRepository([lead]))

    updated = await service.update_lead(lead.id, LeadUpdate.model_validate({"status": "contacted"}))

    assert updated.status is LeadStatus.CONTACTED
    assert updated.staff_notes == "old"


async def test_update_lead_with_null_status_raises_invalid_update() -> None:
    lead = make_lead()
    service, _, _ = build_service(FakeLeadRepository([lead]))

    with pytest.raises(AppError) as exc_info:
        await service.update_lead(lead.id, LeadUpdate.model_validate({"status": None}))

    assert exc_info.value.code == "invalid_update"


async def test_delete_lead_removes_it() -> None:
    lead = make_lead()
    service, repo, _ = build_service(FakeLeadRepository([lead]))

    await service.delete_lead(lead.id)

    assert lead.id not in repo.leads


async def test_get_unknown_lead_raises_not_found() -> None:
    service, _, _ = build_service()

    with pytest.raises(NotFoundError):
        await service.get_lead(uuid.uuid4())


async def test_list_leads_returns_page() -> None:
    service, _, _ = build_service(FakeLeadRepository([make_lead() for _ in range(3)]))

    page = await service.list_leads(LeadFilters(), PageParams(page=1, size=2))

    assert page.total == 3
    assert len(page.items) == 2


@pytest.mark.parametrize(
    ("marketing", "expected"), [(False, ("contact",)), (True, ("contact", "marketing"))]
)
async def test_create_valuation_emits_consent_with_given_purposes(
    marketing: bool, expected: tuple[str, ...]
) -> None:
    service, _, publisher = build_service()
    payload = valuation_payload(consent=consent_payload(marketing_accepted=marketing))

    created = await service.create_valuation(ValuationCreate.model_validate(payload))

    assert isinstance(publisher, InMemoryEventPublisher)
    consent_event = publisher.events[-1]
    assert consent_event.payload.lead_id == created.lead.id
    assert consent_event.payload.purposes == expected
    assert consent_event.payload.policy_version == "2026-01"
    assert consent_event.payload.given_at == NOW


async def test_create_owner_request_with_user_links_account() -> None:
    service, repo, _ = build_service()
    user_id = uuid.uuid4()

    lead = await service.create_owner_request(
        OwnerRequestCreate.model_validate(owner_request_payload()), user_id
    )

    assert repo.leads[lead.id].user_id == user_id


async def test_create_valuation_without_user_has_no_account() -> None:
    service, repo, _ = build_service()

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert repo.leads[created.lead.id].user_id is None


async def test_list_my_requests_returns_only_own_requests() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    own = make_lead(user_id=mine)
    service, _, _ = build_service(FakeLeadRepository([own, make_lead(user_id=other), make_lead()]))

    page = await service.list_my_requests(mine, PageParams())

    assert [item.id for item in page.items] == [own.id]
    assert "staff_notes" not in page.items[0].model_dump()


async def test_delete_user_requests_twice_deletes_once() -> None:
    user_id = uuid.uuid4()
    service, repo, _ = build_service(FakeLeadRepository([make_lead(user_id=user_id), make_lead()]))
    await service.delete_user_requests(user_id)

    deleted_again = await service.delete_user_requests(user_id)

    assert deleted_again == 0
    assert len(repo.leads) == 1


async def test_create_callback_request_stores_contact_details_without_property() -> None:
    service, repo, _ = build_service()

    lead = await service.create_callback_request(
        CallbackRequestCreate.model_validate(callback_request_payload())
    )

    stored = repo.leads[lead.id]
    assert stored.kind is LeadKind.CALLBACK
    assert stored.full_name == "Luca Neri"
    assert stored.phone == "+393334445555"
    assert stored.email == "luca.neri@example.com"
    assert stored.municipality is None
    assert stored.property_type is None
    assert stored.intention is None
    assert stored.details == {"preferred_time": "morning", "source": "website"}
    assert repo.commits == 1


async def test_create_callback_request_is_due_for_contact_immediately() -> None:
    service, repo, _ = build_service()

    lead = await service.create_callback_request(
        CallbackRequestCreate.model_validate(callback_request_payload())
    )

    assert repo.leads[lead.id].next_contact_at == NOW
    assert repo.leads[lead.id].priority is LeadPriority.MEDIUM


async def test_create_callback_request_with_empty_message_stores_none() -> None:
    service, repo, _ = build_service()

    lead = await service.create_callback_request(
        CallbackRequestCreate.model_validate(callback_request_payload(message="   "))
    )

    assert repo.leads[lead.id].message is None


async def test_every_new_request_notifies_the_agency() -> None:
    notifier = RecordingNotifier()
    repo = FakeLeadRepository()
    service = LeadService(
        repo, InMemoryEventPublisher(), WINDOW, clock=lambda: NOW, notifier=notifier
    )

    await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))
    await service.create_owner_request(OwnerRequestCreate.model_validate(owner_request_payload()))
    await service.create_callback_request(
        CallbackRequestCreate.model_validate(callback_request_payload())
    )

    assert [lead.kind for lead in notifier.notified] == [
        LeadKind.VALUATION,
        LeadKind.SELL,
        LeadKind.CALLBACK,
    ]


async def test_create_callback_request_with_failing_email_still_stores_the_lead() -> None:
    repo = FakeLeadRepository()
    service = LeadService(
        repo, InMemoryEventPublisher(), WINDOW, clock=lambda: NOW, notifier=FailingNotifier()
    )

    lead = await service.create_callback_request(
        CallbackRequestCreate.model_validate(callback_request_payload())
    )

    assert lead.id in repo.leads
    assert repo.commits == 1
