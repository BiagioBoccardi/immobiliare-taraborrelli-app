import uuid
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import ConsentRecord
from app.models.enums import ConsentSubject


class ConsentRepository(Protocol):
    async def add(self, record: ConsentRecord) -> ConsentRecord: ...

    async def add_from_event(self, record: ConsentRecord) -> bool: ...

    async def history(
        self, subject_type: ConsentSubject, subject_id: uuid.UUID
    ) -> list[ConsentRecord]: ...

    async def delete_for_subject(
        self, subject_type: ConsentSubject, subject_id: uuid.UUID
    ) -> None: ...


class SqlConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConsentRecord) -> ConsentRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_from_event(self, record: ConsentRecord) -> bool:
        """Insert unless the same event/purpose was already stored. Returns True if inserted."""
        statement = (
            insert(ConsentRecord)
            .values(
                id=record.id,
                subject_type=record.subject_type,
                subject_id=record.subject_id,
                purpose=record.purpose,
                granted=record.granted,
                policy_version=record.policy_version,
                source=record.source,
                recorded_at=record.recorded_at,
                source_event_id=record.source_event_id,
            )
            .on_conflict_do_nothing(constraint="uq_consent_records_event_purpose")
            .returning(ConsentRecord.id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def history(
        self, subject_type: ConsentSubject, subject_id: uuid.UUID
    ) -> list[ConsentRecord]:
        rows = await self._session.scalars(
            select(ConsentRecord)
            .where(
                ConsentRecord.subject_type == subject_type,
                ConsentRecord.subject_id == subject_id,
            )
            .order_by(ConsentRecord.recorded_at, ConsentRecord.created_at)
        )
        return list(rows)

    async def delete_for_subject(self, subject_type: ConsentSubject, subject_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(ConsentRecord).where(
                ConsentRecord.subject_type == subject_type,
                ConsentRecord.subject_id == subject_id,
            )
        )
