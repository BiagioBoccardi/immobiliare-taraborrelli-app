import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ConsentPurpose, ConsentSource, ConsentSubject
from app.models.types import pg_enum, utcnow


class ConsentRecord(Base):
    """Append-only consent registry: every grant or withdrawal is a new row.

    The current state for a purpose is the most recent record. Subjects are either app
    users or leads (owners without an account), referenced by id without a foreign key.
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_consent_records_subject", "subject_type", "subject_id", "purpose"),
        # Makes the lead event consumer idempotent: an event is stored once per purpose.
        UniqueConstraint("source_event_id", "purpose", name="uq_consent_records_event_purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[ConsentSubject] = mapped_column(pg_enum(ConsentSubject, "consent_subject"))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[ConsentPurpose] = mapped_column(pg_enum(ConsentPurpose, "consent_purpose"))
    granted: Mapped[bool] = mapped_column(Boolean)
    policy_version: Mapped[str] = mapped_column(String(20))
    source: Mapped[ConsentSource] = mapped_column(pg_enum(ConsentSource, "consent_source"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
