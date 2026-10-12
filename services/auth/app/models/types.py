from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Enum


def utcnow() -> datetime:
    return datetime.now(UTC)


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )
