"""Result of an action on many properties at once (from the admin list)."""

import uuid

from pydantic import BaseModel


class BulkSkipped(BaseModel):
    id: uuid.UUID
    reference: str
    title: str
    reason: str  # error code, translated by the admin panel (e.g. "photo_required")


class BulkResult(BaseModel):
    done: int
    skipped: list[BulkSkipped]
