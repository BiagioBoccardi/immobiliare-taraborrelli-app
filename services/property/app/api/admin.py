"""Admin panel: the agency publishes and edits properties without a developer."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from py_common.pagination import Page, PageParams, page_params

from app.core.config import Settings
from app.core.dependencies import get_property_service, get_settings_dep, require_staff
from app.models.enums import Contract, PropertyStatus
from app.schemas.property import (
    AdminFilters,
    AdminPropertyOut,
    PhotoOrder,
    PhotoUpdate,
    PropertyCreate,
    PropertyUpdate,
    StatusChange,
)
from app.services.properties import PropertyService

router = APIRouter(
    prefix="/admin/properties", tags=["admin"], dependencies=[Depends(require_staff)]
)

Service = Annotated[PropertyService, Depends(get_property_service)]


@router.get("", response_model=Page[AdminPropertyOut])
async def list_properties(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    status_filter: Annotated[PropertyStatus | None, Query(alias="status")] = None,
    contract: Contract | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> Page[AdminPropertyOut]:
    filters = AdminFilters(status=status_filter, contract=contract, q=q)
    return await service.list_admin(filters, params)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AdminPropertyOut)
async def create_property(data: PropertyCreate, service: Service) -> AdminPropertyOut:
    return await service.create(data)


@router.get("/{property_id}", response_model=AdminPropertyOut)
async def get_property(property_id: uuid.UUID, service: Service) -> AdminPropertyOut:
    return await service.get_admin(property_id)


@router.patch("/{property_id}", response_model=AdminPropertyOut)
async def update_property(
    property_id: uuid.UUID, changes: PropertyUpdate, service: Service
) -> AdminPropertyOut:
    return await service.update(property_id, changes)


@router.post("/{property_id}/status", response_model=AdminPropertyOut)
async def change_status(
    property_id: uuid.UUID, change: StatusChange, service: Service
) -> AdminPropertyOut:
    return await service.change_status(property_id, change.status)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: uuid.UUID, service: Service) -> Response:
    await service.delete(property_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{property_id}/photos", status_code=status.HTTP_201_CREATED, response_model=AdminPropertyOut
)
async def upload_photo(
    property_id: uuid.UUID,
    service: Service,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form(max_length=200)] = None,
) -> AdminPropertyOut:
    # Read one byte more than allowed, so oversized files are rejected without loading them.
    data = await file.read(settings.max_photo_bytes + 1)
    return await service.add_photo(property_id, data, caption)


@router.patch("/{property_id}/photos/{photo_id}", response_model=AdminPropertyOut)
async def update_photo(
    property_id: uuid.UUID, photo_id: uuid.UUID, changes: PhotoUpdate, service: Service
) -> AdminPropertyOut:
    return await service.update_photo(property_id, photo_id, changes)


@router.put("/{property_id}/photos/order", response_model=AdminPropertyOut)
async def reorder_photos(
    property_id: uuid.UUID, order: PhotoOrder, service: Service
) -> AdminPropertyOut:
    return await service.reorder_photos(property_id, order)


@router.delete("/{property_id}/photos/{photo_id}", response_model=AdminPropertyOut)
async def delete_photo(
    property_id: uuid.UUID, photo_id: uuid.UUID, service: Service
) -> AdminPropertyOut:
    return await service.delete_photo(property_id, photo_id)
