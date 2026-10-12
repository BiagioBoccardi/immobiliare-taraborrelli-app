"""Versioned event envelope shared by all services.

Event names follow `<domain>.<past_tense_fact>`. Consumers must be idempotent and can use
`event_id` to discard duplicates.
"""

import uuid
from datetime import UTC, datetime
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field


class EventPayload(BaseModel):
    """Base class for event payloads. Subclasses declare `event_type` and `version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: ClassVar[str]
    version: ClassVar[int] = 1


class Event[P: EventPayload](BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    version: int
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str
    payload: P

    @classmethod
    def wrap(cls, payload: P, producer: str) -> Self:
        return cls(
            event_type=payload.event_type,
            version=payload.version,
            producer=producer,
            payload=payload,
        )

    @property
    def routing_key(self) -> str:
        return f"{self.event_type}.v{self.version}"
