import uuid
from datetime import UTC, datetime, timedelta

import pytest
from py_common.security import Role
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ConsentPurpose, ConsentSubject
from app.repositories.consents import SqlConsentRepository
from app.repositories.refresh_tokens import SqlRefreshTokenRepository
from app.repositories.users import SqlUserRepository
from tests.factories import make_consent, make_refresh_token, make_user

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


async def test_get_by_email_is_case_insensitive(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    user = await repo.add(make_user(email="anna@example.com"))

    found = await repo.get_by_email("ANNA@example.com")

    assert found is not None
    assert found.id == user.id


async def test_duplicate_email_is_rejected_by_database(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    await repo.add(make_user(email="anna@example.com"))

    with pytest.raises(IntegrityError):
        await repo.add(make_user(email="anna@example.com"))


async def test_list_filters_by_role_and_paginates(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    for i in range(3):
        await repo.add(make_user(role=Role.STAFF, created_at=NOW - timedelta(minutes=i)))
    await repo.add(make_user())

    items, total = await repo.list(Role.STAFF, offset=0, limit=2)

    assert total == 3
    assert len(items) == 2
    assert items[0].created_at > items[1].created_at


async def test_count_active_admins_ignores_disabled(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    await repo.add(make_user(role=Role.ADMIN))
    await repo.add(make_user(role=Role.ADMIN, is_active=False))

    count = await repo.count_active_admins()

    assert count == 1


async def test_deleting_user_cascades_to_refresh_tokens(db_session: AsyncSession) -> None:
    users = SqlUserRepository(db_session)
    tokens = SqlRefreshTokenRepository(db_session)
    user = await users.add(make_user())
    await tokens.add(make_refresh_token(user, "t"))

    await users.delete(user)

    db_session.expunge_all()
    assert await tokens.get_by_hash(make_refresh_token(user, "t").token_hash) is None


async def test_revoke_family_revokes_only_that_family(db_session: AsyncSession) -> None:
    users = SqlUserRepository(db_session)
    tokens = SqlRefreshTokenRepository(db_session)
    user = await users.add(make_user())
    family = uuid.uuid4()
    first = await tokens.add(make_refresh_token(user, "a", family_id=family))
    second = await tokens.add(make_refresh_token(user, "b", family_id=family))
    other = await tokens.add(make_refresh_token(user, "c"))

    await tokens.revoke_family(family, NOW)

    for token in (first, second, other):
        await db_session.refresh(token)
    assert first.revoked_at == NOW
    assert second.revoked_at == NOW
    assert other.revoked_at is None


async def test_revoke_all_for_user_revokes_every_session(db_session: AsyncSession) -> None:
    users = SqlUserRepository(db_session)
    tokens = SqlRefreshTokenRepository(db_session)
    user = await users.add(make_user())
    first = await tokens.add(make_refresh_token(user, "a"))
    second = await tokens.add(make_refresh_token(user, "b"))

    await tokens.revoke_all_for_user(user.id, NOW)

    await db_session.refresh(first)
    await db_session.refresh(second)
    assert (first.revoked_at, second.revoked_at) == (NOW, NOW)


async def test_add_from_event_is_idempotent(db_session: AsyncSession) -> None:
    repo = SqlConsentRepository(db_session)
    lead_id, event_id = uuid.uuid4(), uuid.uuid4()
    record = make_consent(lead_id, subject_type=ConsentSubject.LEAD, source_event_id=event_id)
    await repo.add_from_event(record)

    inserted = await repo.add_from_event(
        make_consent(lead_id, subject_type=ConsentSubject.LEAD, source_event_id=event_id)
    )

    assert inserted is False
    assert len(await repo.history(ConsentSubject.LEAD, lead_id)) == 1


async def test_history_is_ordered_from_oldest(db_session: AsyncSession) -> None:
    repo = SqlConsentRepository(db_session)
    user_id = uuid.uuid4()
    await repo.add(make_consent(user_id, recorded_at=NOW))
    await repo.add(
        make_consent(user_id, purpose=ConsentPurpose.MARKETING, recorded_at=NOW - timedelta(1))
    )

    history = await repo.history(ConsentSubject.USER, user_id)

    assert [r.purpose for r in history] == [ConsentPurpose.MARKETING, ConsentPurpose.CONTACT]


async def test_delete_for_subject_keeps_other_subjects(db_session: AsyncSession) -> None:
    repo = SqlConsentRepository(db_session)
    kept, removed = uuid.uuid4(), uuid.uuid4()
    await repo.add(make_consent(kept))
    await repo.add(make_consent(removed))

    await repo.delete_for_subject(ConsentSubject.USER, removed)

    assert await repo.history(ConsentSubject.USER, removed) == []
    assert len(await repo.history(ConsentSubject.USER, kept)) == 1
