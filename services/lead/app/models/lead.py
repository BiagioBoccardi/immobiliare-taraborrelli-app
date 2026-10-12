import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import (
    LeadKind,
    LeadPriority,
    LeadStatus,
    OwnerIntention,
    PropertyCondition,
    PropertyType,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum[E: type](enum_cls: E, name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class Lead(Base):
    """An owner who contacted the agency. A valuation request is a lead, not a mandate."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[LeadKind] = mapped_column(_enum(LeadKind, "lead_kind"), index=True)
    status: Mapped[LeadStatus] = mapped_column(
        _enum(LeadStatus, "lead_status"), default=LeadStatus.NEW, index=True
    )
    priority: Mapped[LeadPriority] = mapped_column(_enum(LeadPriority, "lead_priority"), index=True)
    intention: Mapped[OwnerIntention] = mapped_column(_enum(OwnerIntention, "owner_intention"))

    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(254))

    municipality: Mapped[str] = mapped_column(String(80))
    property_type: Mapped[PropertyType] = mapped_column(_enum(PropertyType, "property_type"))
    surface_sqm: Mapped[int | None] = mapped_column(Integer)
    rooms: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[PropertyCondition | None] = mapped_column(
        _enum(PropertyCondition, "property_condition")
    )
    # Optional information added in the second step (valuations) or as free notes.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    message: Mapped[str | None] = mapped_column(Text)

    # Hash of the one-time token that lets the owner complete the optional second step.
    completion_token_hash: Mapped[str | None] = mapped_column(String(64))

    contact_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    privacy_policy_version: Mapped[str] = mapped_column(String(20))
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)

    next_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    staff_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
