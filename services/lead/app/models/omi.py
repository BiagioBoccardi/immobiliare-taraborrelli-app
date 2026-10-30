from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OmiState, OmiType

# [polygon][ring][point] with points as [longitude, latitude]; the first ring is the outer one.
Polygons = list[list[list[list[float]]]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum[E: type](enum_cls: E, name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class OmiImport(Base):
    """One upload of the OMI files from the admin panel. The latest one is in use."""

    __tablename__ = "omi_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester: Mapped[str] = mapped_column(String(10))  # e.g. "2026/1"
    quotes: Mapped[int] = mapped_column(Integer)
    zones: Mapped[int] = mapped_column(Integer)
    municipalities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class OmiQuote(Base):
    """Sale value range (€/m²) of a residential type in an OMI zone."""

    __tablename__ = "omi_quotes"
    __table_args__ = (Index("ix_omi_quotes_zone", "municipality_code", "zone_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality_code: Mapped[str] = mapped_column(String(6))  # cadastral code, e.g. C632
    municipality: Mapped[str] = mapped_column(String(80))
    zone_code: Mapped[str] = mapped_column(String(10))  # e.g. B1
    zone_description: Mapped[str | None] = mapped_column(String(300))
    omi_type: Mapped[OmiType] = mapped_column(_enum(OmiType, "omi_type"))
    state: Mapped[OmiState] = mapped_column(_enum(OmiState, "omi_state"))
    prevalent: Mapped[bool] = mapped_column(Boolean, default=False)
    sale_min: Mapped[float] = mapped_column(Float)
    sale_max: Mapped[float] = mapped_column(Float)


class OmiZone(Base):
    """Perimeter of an OMI zone, to find the zone of an address."""

    __tablename__ = "omi_zones"
    __table_args__ = (Index("ix_omi_zones_bbox", "min_lon", "max_lon", "min_lat", "max_lat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality_code: Mapped[str] = mapped_column(String(6))
    zone_code: Mapped[str] = mapped_column(String(10))
    polygons: Mapped[Any] = mapped_column(JSONB)
    min_lon: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
