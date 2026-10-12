"""CRM endpoints for the admin panel. Every endpoint requires the staff role."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from py_common.pagination import Page, PageParams, page_params

from app.core.dependencies import get_lead_service, require_staff
from app.models.enums import LeadKind, LeadPriority, LeadStatus
from app.schemas.lead import LeadFilters, LeadOut, LeadUpdate
from app.services.lead import LeadService

router = APIRouter(prefix="/leads", tags=["staff"], dependencies=[Depends(require_staff)])

Service = Annotated[LeadService, Depends(get_lead_service)]


@router.get("", response_model=Page[LeadOut])
async def list_leads(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    kind: LeadKind | None = None,
    status: LeadStatus | None = None,
    priority: LeadPriority | None = None,
    due_for_contact: bool = False,
) -> Page[LeadOut]:
    filters = LeadFilters(
        kind=kind, status=status, priority=priority, due_for_contact=due_for_contact
    )
    return await service.list_leads(filters, params)


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: uuid.UUID, service: Service) -> LeadOut:
    return LeadOut.model_validate(await service.get_lead(lead_id))


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: uuid.UUID, changes: LeadUpdate, service: Service) -> LeadOut:
    return LeadOut.model_validate(await service.update_lead(lead_id, changes))


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: uuid.UUID, service: Service) -> Response:
    await service.delete_lead(lead_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
