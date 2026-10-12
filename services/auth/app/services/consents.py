import uuid

from py_common.events import Event
from py_common.events.lead import LeadConsentGivenV1

from app.models.consent import ConsentRecord
from app.models.enums import ConsentPurpose, ConsentSource, ConsentSubject
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.auth import ConsentChange, ConsentStatus
from app.services.clock import Clock, utcnow


def current_state(records: list[ConsentRecord]) -> list[ConsentStatus]:
    """Latest record per purpose. `records` must be ordered from oldest to newest."""
    latest: dict[ConsentPurpose, ConsentRecord] = {}
    for record in records:
        latest[record.purpose] = record
    return [
        ConsentStatus(
            purpose=record.purpose,
            granted=record.granted,
            policy_version=record.policy_version,
            recorded_at=record.recorded_at,
        )
        for record in sorted(latest.values(), key=lambda r: r.purpose.value)
    ]


class ConsentService:
    def __init__(self, uow: UnitOfWork, clock: Clock = utcnow) -> None:
        self._uow = uow
        self._clock = clock

    async def record_user_consent(
        self,
        user_id: uuid.UUID,
        purpose: ConsentPurpose,
        granted: bool,
        policy_version: str,
        source: ConsentSource,
    ) -> ConsentRecord:
        """Adds a record without committing, so it can join a larger transaction."""
        return await self._uow.consents.add(
            ConsentRecord(
                id=uuid.uuid4(),
                subject_type=ConsentSubject.USER,
                subject_id=user_id,
                purpose=purpose,
                granted=granted,
                policy_version=policy_version,
                source=source,
                recorded_at=self._clock(),
            )
        )

    async def change(self, user_id: uuid.UUID, change: ConsentChange) -> list[ConsentStatus]:
        await self.record_user_consent(
            user_id, change.purpose, change.granted, change.policy_version, change.source
        )
        await self._uow.commit()
        return await self.current_for_user(user_id)

    async def current_for_user(self, user_id: uuid.UUID) -> list[ConsentStatus]:
        return current_state(await self._uow.consents.history(ConsentSubject.USER, user_id))

    async def record_lead_consent(self, event: Event[LeadConsentGivenV1]) -> int:
        """Stores the consents of a lead form. Idempotent: returns how many rows were new."""
        inserted = 0
        for purpose in event.payload.purposes:
            created = await self._uow.consents.add_from_event(
                ConsentRecord(
                    id=uuid.uuid4(),
                    subject_type=ConsentSubject.LEAD,
                    subject_id=event.payload.lead_id,
                    purpose=ConsentPurpose(purpose),
                    granted=True,
                    policy_version=event.payload.policy_version,
                    source=ConsentSource.LEAD_FORM,
                    recorded_at=event.payload.given_at,
                    source_event_id=event.event_id,
                )
            )
            inserted += int(created)
        await self._uow.commit()
        return inserted
