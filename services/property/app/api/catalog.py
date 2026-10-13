"""Public catalog: no login needed to browse (section 11)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from py_common.pagination import Page, PageParams, page_params
from pydantic import ValidationError

from app.core.dependencies import get_property_service
from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    Feature,
    PropertyType,
    SortOrder,
    TenantType,
)
from app.schemas.property import PropertyCard, PropertyDetail, SearchFilters, SoldCard
from app.services.properties import PropertyService

router = APIRouter(tags=["catalog"])

Service = Annotated[PropertyService, Depends(get_property_service)]
Paging = Annotated[PageParams, Depends(page_params)]


def search_filters(
    contract: Contract | None = None,
    property_type: Annotated[list[PropertyType] | None, Query()] = None,
    municipality: Annotated[str | None, Query(max_length=80)] = None,
    zone: Annotated[str | None, Query(max_length=80)] = None,
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    surface_min: Annotated[int | None, Query(ge=0)] = None,
    surface_max: Annotated[int | None, Query(ge=0)] = None,
    rooms_min: Annotated[int | None, Query(ge=0)] = None,
    bedrooms_min: Annotated[int | None, Query(ge=0)] = None,
    bathrooms_min: Annotated[int | None, Query(ge=0)] = None,
    feature: Annotated[list[Feature] | None, Query()] = None,
    energy_class: Annotated[list[EnergyClass] | None, Query()] = None,
    featured: bool | None = None,
    tenant_type: TenantType | None = None,
    accommodation: Accommodation | None = None,
    available_by: date | None = None,
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    sort: SortOrder = SortOrder.NEWEST,
) -> SearchFilters:
    try:
        return _validate_filters(
            {
                "contract": contract,
                "property_types": property_type or [],
                "municipality": municipality,
                "zone": zone,
                "price_min": price_min,
                "price_max": price_max,
                "surface_min": surface_min,
                "surface_max": surface_max,
                "rooms_min": rooms_min,
                "bedrooms_min": bedrooms_min,
                "bathrooms_min": bathrooms_min,
                "features": feature or [],
                "energy_classes": energy_class or [],
                "featured": featured,
                "tenant_type": tenant_type,
                "accommodation": accommodation,
                "available_by": available_by,
                "min_lat": None if min_lat is None else str(min_lat),
                "max_lat": None if max_lat is None else str(max_lat),
                "min_lng": None if min_lng is None else str(min_lng),
                "max_lng": None if max_lng is None else str(max_lng),
                "sort": sort,
            }
        )
    except ValidationError as exc:
        # Cross-field errors (e.g. incomplete map viewport) become a normal 422.
        raise RequestValidationError(
            [{**error, "loc": ("query", *error["loc"])} for error in exc.errors()]
        ) from exc


def _validate_filters(values: dict[str, object]) -> SearchFilters:
    return SearchFilters.model_validate(values)


@router.get("/properties", response_model=Page[PropertyCard])
async def search_properties(
    service: Service,
    params: Paging,
    filters: Annotated[SearchFilters, Depends(search_filters)],
) -> Page[PropertyCard]:
    return await service.search(filters, params)


@router.get("/properties/{property_id}", response_model=PropertyDetail)
async def get_property(property_id: uuid.UUID, service: Service) -> PropertyDetail:
    return await service.get_public(property_id)


@router.get("/sold", response_model=Page[SoldCard])
async def list_sold(service: Service, params: Paging) -> Page[SoldCard]:
    return await service.list_sold(params)
