import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import (
    LeadKind,
    LeadPriority,
    LeadStatus,
    OwnerIntention,
    PropertyCondition,
    PropertyType,
)
from app.schemas.common import EmailText, Municipality, PersonName, Phone, PolicyVersion

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class ConsentIn(BaseModel):
    """Consent given when the form is submitted. Contact consent is mandatory (GDPR)."""

    privacy_accepted: Literal[True]
    privacy_policy_version: PolicyVersion
    marketing_accepted: bool = False


class ValuationCreate(BaseModel):
    """First step of "Quanto vale la tua casa?": only the essential data."""

    model_config = ConfigDict(extra="forbid")

    full_name: PersonName
    phone: Phone
    municipality: Municipality
    property_type: PropertyType
    surface_sqm: int = Field(ge=10, le=5000, description="Approximate surface in square meters")
    rooms: int = Field(ge=1, le=30)
    condition: PropertyCondition
    intention: OwnerIntention
    consent: ConsentIn


class SellTimeline(StrEnum):
    IMMEDIATELY = "immediately"
    WITHIN_3_MONTHS = "within_3_months"
    WITHIN_6_MONTHS = "within_6_months"
    WITHIN_12_MONTHS = "within_12_months"
    NOT_SURE = "not_sure"


class PartCondition(StrEnum):
    TO_RENOVATE = "to_renovate"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class EnergyClass(StrEnum):
    A4 = "A4"
    A3 = "A3"
    A2 = "A2"
    A1 = "A1"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class PartsCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kitchen: PartCondition | None = None
    bathrooms: PartCondition | None = None
    windows: PartCondition | None = None
    systems: PartCondition | None = None


class ValuationDetails(BaseModel):
    """Optional second step. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    email: EmailText | None = None
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    floor: int | None = Field(default=None, ge=-2, le=60)
    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_garden: bool | None = None
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    energy_class: EnergyClass | None = None
    sell_timeline: SellTimeline | None = None
    expected_price: int | None = Field(default=None, ge=0, le=100_000_000)
    expected_price_unknown: bool = False
    parts_condition: PartsCondition | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _price_or_unknown(self) -> "ValuationDetails":
        if self.expected_price_unknown and self.expected_price is not None:
            raise ValueError("expected_price must be empty when expected_price_unknown is true")
        return self


class OwnerRequestCreate(BaseModel):
    """ "Voglio vendere casa" / "Voglio affittare il mio immobile": short form."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[LeadKind.SELL, LeadKind.RENT]
    full_name: PersonName
    phone: Phone
    municipality: Municipality
    property_type: PropertyType
    intention: OwnerIntention
    surface_sqm: int | None = Field(default=None, ge=10, le=5000)
    rooms: int | None = Field(default=None, ge=1, le=30)
    message: Notes | None = None
    consent: ConsentIn


class LeadCreatedOut(BaseModel):
    id: uuid.UUID
    kind: LeadKind
    created_at: datetime


class ValuationCreatedOut(LeadCreatedOut):
    completion_token: str = Field(
        description="One-time secret required to add the optional details. Shown only once."
    )
    completion_expires_at: datetime


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: LeadKind
    status: LeadStatus
    priority: LeadPriority
    intention: OwnerIntention
    full_name: str
    phone: str
    email: str | None
    municipality: str
    property_type: PropertyType
    surface_sqm: int | None
    rooms: int | None
    condition: PropertyCondition | None
    details: dict[str, object]
    message: str | None
    marketing_consent: bool
    privacy_policy_version: str
    contact_consent_at: datetime
    next_contact_at: datetime | None
    staff_notes: str | None
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    """CRM update made by staff. Only the fields that are sent are changed."""

    model_config = ConfigDict(extra="forbid")

    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    next_contact_at: datetime | None = None
    staff_notes: Notes | None = None
    email: EmailText | None = None

    @model_validator(mode="after")
    def _aware_datetime(self) -> "LeadUpdate":
        if self.next_contact_at is not None and self.next_contact_at.tzinfo is None:
            raise ValueError("next_contact_at must include a timezone")
        return self


class LeadFilters(BaseModel):
    kind: LeadKind | None = None
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    due_for_contact: bool = False
