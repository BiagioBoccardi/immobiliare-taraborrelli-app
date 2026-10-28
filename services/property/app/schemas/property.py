import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    Feature,
    PropertyCondition,
    PropertyStatus,
    PropertyType,
    SortOrder,
    TenantType,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]
Place = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
# Code of the listing in the agency's management software (e.g. Reasoft).
ExternalRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Caption = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)]

RENTAL_ONLY_FIELDS = ("tenant_types", "accommodation", "available_from")


class PropertyFields(BaseModel):
    """Every editable field. Used to validate the property as a whole after a change."""

    model_config = ConfigDict(extra="forbid")

    contract: Contract
    property_type: PropertyType
    external_ref: ExternalRef | None = None
    title: Title
    description: Description = ""
    price: int = Field(ge=0, le=100_000_000)
    condominium_fees: int | None = Field(default=None, ge=0, le=100_000)
    # Optional for drafts only: publishing requires it (see PropertyService.change_status).
    surface_sqm: int | None = Field(default=None, ge=1, le=100_000)
    rooms: int | None = Field(default=None, ge=0, le=100)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: int | None = Field(default=None, ge=0, le=50)
    floor: int | None = Field(default=None, ge=-3, le=100)
    total_floors: int | None = Field(default=None, ge=0, le=100)
    year_built: int | None = Field(default=None, ge=1000, le=2100)
    condition: PropertyCondition | None = None
    energy_class: EnergyClass | None = None
    features: list[Feature] = Field(default_factory=list, max_length=len(Feature))
    is_featured: bool = False
    municipality: Place
    zone: Place | None = None
    address: Address | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    show_exact_location: bool = False
    tenant_types: list[TenantType] = Field(default_factory=list, max_length=len(TenantType))
    accommodation: Accommodation | None = None
    available_from: date | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        if self.contract is Contract.SALE:
            used = [name for name in RENTAL_ONLY_FIELDS if getattr(self, name)]
            if used:
                raise ValueError(f"{', '.join(used)} are only allowed for rentals")
        if self.floor is not None and self.total_floors is not None:
            if self.floor > self.total_floors:
                raise ValueError("floor cannot be higher than total_floors")
        self.features = sorted(set(self.features))
        self.tenant_types = sorted(set(self.tenant_types))
        return self


class PropertyCreate(PropertyFields):
    pass


class PropertyUpdate(BaseModel):
    """Partial change: only the fields that are sent are changed, then the whole is revalidated."""

    model_config = ConfigDict(extra="forbid")

    contract: Contract | None = None
    property_type: PropertyType | None = None
    external_ref: ExternalRef | None = None
    title: Title | None = None
    description: Description | None = None
    price: int | None = Field(default=None, ge=0, le=100_000_000)
    condominium_fees: int | None = Field(default=None, ge=0, le=100_000)
    surface_sqm: int | None = Field(default=None, ge=1, le=100_000)
    rooms: int | None = Field(default=None, ge=0, le=100)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: int | None = Field(default=None, ge=0, le=50)
    floor: int | None = Field(default=None, ge=-3, le=100)
    total_floors: int | None = Field(default=None, ge=0, le=100)
    year_built: int | None = Field(default=None, ge=1000, le=2100)
    condition: PropertyCondition | None = None
    energy_class: EnergyClass | None = None
    features: list[Feature] | None = None
    is_featured: bool | None = None
    municipality: Place | None = None
    zone: Place | None = None
    address: Address | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    show_exact_location: bool | None = None
    tenant_types: list[TenantType] | None = None
    accommodation: Accommodation | None = None
    available_from: date | None = None


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PropertyStatus


class PhotoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption: Caption | None = None
    show_when_sold: bool | None = None


class PhotoOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    photo_ids: list[uuid.UUID] = Field(min_length=1)


class PhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    caption: str | None
    # 3D version of the room in the photo, when there is one (binary glTF).
    three_d_url: str | None = None


class AdminPhotoOut(PhotoOut):
    position: int
    show_when_sold: bool
    content_type: str
    size_bytes: int


class ThreeDModelOut(BaseModel):
    """3D model of the property (binary glTF, .glb)."""

    url: str
    size_bytes: int


class Coordinates(BaseModel):
    latitude: Decimal
    longitude: Decimal
    exact: bool


class PropertyCard(BaseModel):
    """List item for the catalog, carousels and map."""

    id: uuid.UUID
    reference: str
    status: PropertyStatus
    contract: Contract
    property_type: PropertyType
    title: str
    price: int
    municipality: str
    zone: str | None
    surface_sqm: int
    rooms: int | None
    bedrooms: int | None
    bathrooms: int | None
    is_featured: bool
    cover_photo: PhotoOut | None
    coordinates: Coordinates | None
    available_from: date | None
    published_at: datetime | None


class PropertyDetail(PropertyCard):
    description: str
    condominium_fees: int | None
    floor: int | None
    total_floors: int | None
    year_built: int | None
    condition: PropertyCondition | None
    energy_class: EnergyClass | None
    features: list[Feature]
    tenant_types: list[TenantType]
    accommodation: Accommodation | None
    photos: list[PhotoOut]
    three_d_model: ThreeDModelOut | None


class AdminPropertyOut(BaseModel):
    """Everything the agency can see and edit, including the exact address."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    external_ref: str | None
    status: PropertyStatus
    contract: Contract
    property_type: PropertyType
    title: str
    description: str
    price: int
    condominium_fees: int | None
    surface_sqm: int | None
    rooms: int | None
    bedrooms: int | None
    bathrooms: int | None
    floor: int | None
    total_floors: int | None
    year_built: int | None
    condition: PropertyCondition | None
    energy_class: EnergyClass | None
    features: list[Feature]
    is_featured: bool
    municipality: str
    zone: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    show_exact_location: bool
    tenant_types: list[TenantType]
    accommodation: Accommodation | None
    available_from: date | None
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    photos: list[AdminPhotoOut]
    three_d_model: ThreeDModelOut | None


class SoldCard(BaseModel):
    """ "Immobili venduti": only area, type and authorized photos. No price, no address."""

    id: uuid.UUID
    contract: Contract
    property_type: PropertyType
    municipality: str
    zone: str | None
    closed_on: date | None
    photos: list[PhotoOut]


class SearchFilters(BaseModel):
    contract: Contract | None = None
    property_types: list[PropertyType] = Field(default_factory=list)
    municipality: str | None = None
    zone: str | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    surface_min: int | None = Field(default=None, ge=0)
    surface_max: int | None = Field(default=None, ge=0)
    rooms_min: int | None = Field(default=None, ge=0)
    bedrooms_min: int | None = Field(default=None, ge=0)
    bathrooms_min: int | None = Field(default=None, ge=0)
    features: list[Feature] = Field(default_factory=list)
    energy_classes: list[EnergyClass] = Field(default_factory=list)
    featured: bool | None = None
    tenant_type: TenantType | None = None
    accommodation: Accommodation | None = None
    available_by: date | None = None  # move-in date: available on or before this day
    # Map viewport.
    min_lat: Latitude | None = None
    max_lat: Latitude | None = None
    min_lng: Longitude | None = None
    max_lng: Longitude | None = None
    sort: SortOrder = SortOrder.NEWEST

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        bbox = (self.min_lat, self.max_lat, self.min_lng, self.max_lng)
        if any(v is not None for v in bbox) and any(v is None for v in bbox):
            raise ValueError("min_lat, max_lat, min_lng and max_lng must be given together")
        for low, high in (("price_min", "price_max"), ("surface_min", "surface_max")):
            low_value, high_value = getattr(self, low), getattr(self, high)
            if low_value is not None and high_value is not None and low_value > high_value:
                raise ValueError(f"{low} cannot be greater than {high}")
        return self


class AdminFilters(BaseModel):
    status: PropertyStatus | None = None
    contract: Contract | None = None
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
