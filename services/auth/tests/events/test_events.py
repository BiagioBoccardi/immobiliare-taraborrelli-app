from collections.abc import Callable

from httpx import AsyncClient
from py_common.events import Event, InMemoryEventPublisher
from py_common.events.auth import UserDeletedV1
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.consumers import LeadConsentHandler
from app.events.publisher import LoggingEventPublisher
from app.models.consent import ConsentRecord
from app.models.enums import ConsentSubject
from app.models.user import User
from tests.factories import lead_consent_event


async def _lead_records(session: AsyncSession) -> list[ConsentRecord]:
    rows = await session.scalars(
        select(ConsentRecord).where(ConsentRecord.subject_type == ConsentSubject.LEAD)
    )
    return list(rows)


async def test_lead_consent_handler_stores_consents(
    session_factory: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    event = lead_consent_event(("contact",))

    await LeadConsentHandler(session_factory)(
        "lead.consent_given.v1", event.model_dump_json().encode()
    )

    [record] = await _lead_records(db_session)
    assert record.subject_id == event.payload.lead_id
    assert record.source_event_id == event.event_id


async def test_lead_consent_handler_same_event_twice_stores_once(
    session_factory: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    handler = LeadConsentHandler(session_factory)
    body = lead_consent_event(("contact", "marketing")).model_dump_json().encode()
    await handler("lead.consent_given.v1", body)

    await handler("lead.consent_given.v1", body)

    assert len(await _lead_records(db_session)) == 2


async def test_delete_me_emits_schema_valid_user_deleted_event(
    client: AsyncClient,
    user: User,
    auth_headers: Callable[[User], dict[str, str]],
    publisher: InMemoryEventPublisher,
) -> None:
    await client.delete("/api/v1/auth/me", headers=auth_headers(user))

    [event] = publisher.events
    parsed = Event[UserDeletedV1].model_validate_json(event.model_dump_json())
    assert parsed.routing_key == "auth.user_deleted.v1"
    assert parsed.payload.user_id == user.id
    assert user.email not in event.model_dump_json()


async def test_logging_publisher_accepts_event(user: User) -> None:
    await LoggingEventPublisher().publish(
        Event.wrap(UserDeletedV1(user_id=user.id), producer="auth")
    )
