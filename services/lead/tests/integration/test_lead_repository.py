import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadKind, LeadPriority, LeadStatus
from app.repositories.lead import SqlLeadRepository
from app.schemas.lead import LeadFilters
from tests.factories import make_lead

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


async def test_add_and_get_roundtrip_preserves_fields(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    lead = make_lead(details={"floor": 2})
    await repo.add(lead)
    await repo.commit()
    db_session.expunge_all()

    loaded = await repo.get(lead.id)

    assert loaded is not None
    assert loaded.details == {"floor": 2}
    assert loaded.kind is LeadKind.VALUATION


async def test_list_orders_by_priority_then_newest(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    low = make_lead(priority=LeadPriority.LOW, created_at=NOW)
    high_old = make_lead(priority=LeadPriority.HIGH, created_at=NOW - timedelta(days=1))
    high_new = make_lead(priority=LeadPriority.HIGH, created_at=NOW)
    for lead in (low, high_old, high_new):
        await repo.add(lead)

    items, total = await repo.list(LeadFilters(), NOW, offset=0, limit=10)

    assert total == 3
    assert [lead.id for lead in items] == [high_new.id, high_old.id, low.id]


async def test_list_filters_by_kind_and_status(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    match = make_lead(kind=LeadKind.SELL, status=LeadStatus.CONTACTED)
    await repo.add(match)
    await repo.add(make_lead(kind=LeadKind.SELL))
    await repo.add(make_lead(status=LeadStatus.CONTACTED))

    items, total = await repo.list(
        LeadFilters(kind=LeadKind.SELL, status=LeadStatus.CONTACTED), NOW, offset=0, limit=10
    )

    assert total == 1
    assert items[0].id == match.id


async def test_list_due_for_contact_returns_only_overdue_reminders(
    db_session: AsyncSession,
) -> None:
    repo = SqlLeadRepository(db_session)
    overdue = make_lead(next_contact_at=NOW - timedelta(hours=1))
    await repo.add(overdue)
    await repo.add(make_lead(next_contact_at=NOW + timedelta(days=1)))
    await repo.add(make_lead())

    items, total = await repo.list(LeadFilters(due_for_contact=True), NOW, offset=0, limit=10)

    assert total == 1
    assert items[0].id == overdue.id


async def test_list_paginates_with_total(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    for i in range(5):
        await repo.add(make_lead(created_at=NOW - timedelta(minutes=i)))

    items, total = await repo.list(LeadFilters(), NOW, offset=4, limit=2)

    assert total == 5
    assert len(items) == 1


async def test_delete_removes_row(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    lead = await repo.add(make_lead())

    await repo.delete(lead)

    assert await repo.get(lead.id) is None


async def test_list_for_user_returns_own_newest_first(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    user_id = uuid.uuid4()
    old = await repo.add(make_lead(user_id=user_id, created_at=NOW - timedelta(days=1)))
    new = await repo.add(make_lead(user_id=user_id, created_at=NOW))
    await repo.add(make_lead(user_id=uuid.uuid4()))

    items, total = await repo.list_for_user(user_id, offset=0, limit=10)

    assert total == 2
    assert [lead.id for lead in items] == [new.id, old.id]


async def test_delete_for_user_keeps_other_leads(db_session: AsyncSession) -> None:
    repo = SqlLeadRepository(db_session)
    user_id = uuid.uuid4()
    await repo.add(make_lead(user_id=user_id))
    kept = await repo.add(make_lead())

    deleted = await repo.delete_for_user(user_id)

    assert deleted == 1
    assert await repo.get(kept.id) is not None
