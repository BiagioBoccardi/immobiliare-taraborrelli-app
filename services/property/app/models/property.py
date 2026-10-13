import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    PropertyCondition,
    PropertyStatus,
    PropertyType,
)
from app.models.types import pg_enum, utcnow


class Property(Base):
    """A listing of the agency. No owner data is stored here: owners live in the lead CRM."""

    __tablename__ = "properties"
    __table_args__ = (
        Index("ix_properties_status_contract", "status", "contract"),
        Index("ix_properties_features", "features", postgresql_using="gin"),
        Index("ix_properties_location", "latitude", "longitude"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Sequential number for the human-readable reference shown to clients ("Rif. TR00042").
    number: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    status: Mapped[PropertyStatus] = mapped_column(
        pg_enum(PropertyStatus, "property_status"), default=PropertyStatus.DRAFT
    )
    contract: Mapped[Contract] = mapped_column(pg_enum(Contract, "contract"))
    property_type: Mapped[PropertyType] = mapped_column(
        pg_enum(PropertyType, "property_type"), index=True
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer, index=True)  # euros; monthly rent for rentals
    condominium_fees: Mapped[int | None] = mapped_column(Integer)  # euros per month

    surface_sqm: Mapped[int] = mapped_column(Integer, index=True)
    rooms: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[PropertyCondition | None] = mapped_column(
        pg_enum(PropertyCondition, "property_condition")
    )
    energy_class: Mapped[EnergyClass | None] = mapped_column(pg_enum(EnergyClass, "energy_class"))
    features: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)

    municipality: Mapped[str] = mapped_column(String(80), index=True)
    zone: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(String(200))  # visible to staff only
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # When false, clients receive coordinates rounded to about 100 meters.
    show_exact_location: Mapped[bool] = mapped_column(Boolean, default=False)

    # Rentals for students and workers.
    tenant_types: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    accommodation: Mapped[Accommodation | None] = mapped_column(
        pg_enum(Accommodation, "accommodation")
    )
    available_from: Mapped[date | None] = mapped_column(Date)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # sold/rented
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    photos: Mapped[list["Photo"]] = relationship(
        back_populates="property",
        order_by="Photo.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def reference(self) -> str:
        return f"TR{self.number:05d}"


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(30))
    size_bytes: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)  # 0 is the cover photo
    caption: Mapped[str | None] = mapped_column(String(200))
    # Only authorized photos are shown in "Immobili venduti".
    show_when_sold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    property: Mapped[Property] = relationship(back_populates="photos")
