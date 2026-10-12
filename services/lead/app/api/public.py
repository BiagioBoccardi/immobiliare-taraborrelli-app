"""Public endpoints used by the app and the web valuation page (rate limited at the gateway)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.core.dependencies import get_lead_service
from app.schemas.lead import (
    LeadCreatedOut,
    OwnerRequestCreate,
    ValuationCreate,
    ValuationCreatedOut,
    ValuationDetails,
)
from app.services.lead import LeadService

router = APIRouter(tags=["public"])

Service = Annotated[LeadService, Depends(get_lead_service)]


@router.post("/valuations", status_code=status.HTTP_201_CREATED, response_model=ValuationCreatedOut)
async def create_valuation(data: ValuationCreate, service: Service) -> ValuationCreatedOut:
    created = await service.create_valuation(data)
    return ValuationCreatedOut(
        id=created.lead.id,
        kind=created.lead.kind,
        created_at=created.lead.created_at,
        completion_token=created.completion_token,
        completion_expires_at=created.completion_expires_at,
    )


@router.put("/valuations/{lead_id}/details", status_code=status.HTTP_204_NO_CONTENT)
async def complete_valuation(
    lead_id: uuid.UUID,
    details: ValuationDetails,
    service: Service,
    completion_token: Annotated[str, Header(alias="X-Completion-Token", min_length=1)],
) -> Response:
    await service.complete_valuation(lead_id, completion_token, details)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/owner-requests", status_code=status.HTTP_201_CREATED, response_model=LeadCreatedOut)
async def create_owner_request(data: OwnerRequestCreate, service: Service) -> LeadCreatedOut:
    lead = await service.create_owner_request(data)
    return LeadCreatedOut(id=lead.id, kind=lead.kind, created_at=lead.created_at)
