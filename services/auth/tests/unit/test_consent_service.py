import uuid
from datetime import UTC, datetime, timedelta

from app.models.enums import ConsentPurpose, ConsentSource, ConsentSubject
from app.schemas.auth import ConsentChange
from app.services.consents import ConsentService, current_state
from tests.factories import lead_consent_event, make_consent
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def test_current_state_returns_latest_record_per_purpose() -> None:
    user_id = uuid.uuid4()
    records = [
        make_consent(user_id, purpose=ConsentPurpose.MARKETING, recorded_at=NOW),
        make_consent(user_id, purpose=ConsentPurpose.CONTACT, recorded_at=NOW),
        make_consent(
            user_id,
            purpose=ConsentPurpose.MARKETING,
            granted=False,
            recorded_at=NOW + timedelta(days=1),
        ),
    ]

    state = current_state(records)

    assert [(s.purpose, s.granted) for s in state] == [
        (ConsentPurpose.CONTACT, True),
        (ConsentPurpose.MARKETING, False),
    ]


async def test_change_appends_record_and_returns_state() -> None:
    uow = FakeUnitOfWork()
    user_id = uuid.uuid4()
    service = ConsentService(uow, clock=lambda: NOW)

    state = await service.change(
        user_id,
        ConsentChange(
            purpose=ConsentPurpose.PUSH_NOTIFICATIONS, granted=True, policy_version="2026-01"
        ),
    )

    assert [(s.purpose, s.granted) for s in state] == [(ConsentPurpose.PUSH_NOTIFICATIONS, True)]
    assert uow.consents.items[0].recorded_at == NOW
    assert uow.commits == 1


async def test_record_lead_consent_stores_one_record_per_purpose() -> None:
    uow = FakeUnitOfWork()
    event = lead_consent_event(("contact", "marketing"))

    inserted = await ConsentService(uow).record_lead_consent(event)

    assert inserted == 2
    record = uow.consents.items[0]
    assert record.subject_type is ConsentSubject.LEAD
    assert record.subject_id == event.payload.lead_id
    assert record.source is ConsentSource.LEAD_FORM
    assert record.recorded_at == event.payload.given_at


async def test_record_lead_consent_twice_does_not_duplicate() -> None:
    uow = FakeUnitOfWork()
    service = ConsentService(uow)
    event = lead_consent_event()
    await service.record_lead_consent(event)

    inserted = await service.record_lead_consent(event)

    assert inserted == 0
    assert len(uow.consents.items) == 2
