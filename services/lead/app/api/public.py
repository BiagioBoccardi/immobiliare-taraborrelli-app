"""Public endpoints used by the app and the websites.

The forms are rate limited by the gateway, or by the service itself where there is no
gateway (RATE_LIMIT_ENABLED).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from py_common.pagination import Page, PageParams, page_params
from py_common.security import Principal

from app.core.dependencies import (
    forms_rate_limit,
    get_geocoder,
    get_lead_service,
    optional_user,
    require_user,
)
from app.schemas.lead import (
    CallbackRequestCreate,
    LeadCreatedOut,
    MyRequestOut,
    OwnerRequestCreate,
    PlaceOut,
    ValuationCreate,
    ValuationCreatedOut,
    ValuationDetails,
)
from app.services.geocoding import Geocoder
from app.services.lead import LeadService

router = APIRouter(tags=["public"])

Service = Annotated[LeadService, Depends(get_lead_service)]
OptionalUser = Annotated[Principal | None, Depends(optional_user)]


def _user_id(principal: Principal | None) -> uuid.UUID | None:
    return uuid.UUID(principal.subject) if principal else None


@router.post(
    "/valuations",
    status_code=status.HTTP_201_CREATED,
    response_model=ValuationCreatedOut,
    dependencies=[Depends(forms_rate_limit)],
)
async def create_valuation(
    data: ValuationCreate, service: Service, principal: OptionalUser
) -> ValuationCreatedOut:
    created = await service.create_valuation(data, _user_id(principal))
    return ValuationCreatedOut(
        id=created.lead.id,
        kind=created.lead.kind,
        created_at=created.lead.created_at,
        completion_token=created.completion_token,
        completion_expires_at=created.completion_expires_at,
        estimate=created.estimate,
        estimate_unavailable=created.estimate_unavailable,
    )


@router.get("/geocode", response_model=Page[PlaceOut])
async def geocode(
    geocoder: Annotated[Geocoder, Depends(get_geocoder)],
    q: Annotated[str, Query(min_length=3, max_length=200, description="Address to search")],
) -> Page[PlaceOut]:
    """Addresses matching the text, for the online estimate. Data © OpenStreetMap."""
    places = await geocoder.search(q)
    items = [PlaceOut.model_validate(place) for place in places]
    return Page[PlaceOut](items=items, total=len(items), page=1, size=max(len(items), 1))


@router.put(
    "/valuations/{lead_id}/details",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(forms_rate_limit)],
)
async def complete_valuation(
    lead_id: uuid.UUID,
    details: ValuationDetails,
    service: Service,
    completion_token: Annotated[str, Header(alias="X-Completion-Token", min_length=1)],
) -> Response:
    await service.complete_valuation(lead_id, completion_token, details)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/owner-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=LeadCreatedOut,
    dependencies=[Depends(forms_rate_limit)],
)
async def create_owner_request(
    data: OwnerRequestCreate, service: Service, principal: OptionalUser
) -> LeadCreatedOut:
    lead = await service.create_owner_request(data, _user_id(principal))
    return LeadCreatedOut(id=lead.id, kind=lead.kind, created_at=lead.created_at)


@router.post(
    "/callback-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=LeadCreatedOut,
    dependencies=[Depends(forms_rate_limit)],
)
async def create_callback_request(
    data: CallbackRequestCreate, service: Service, principal: OptionalUser
) -> LeadCreatedOut:
    """ "Richiedi di essere ricontattato" from the agency's website."""
    lead = await service.create_callback_request(data, _user_id(principal))
    return LeadCreatedOut(id=lead.id, kind=lead.kind, created_at=lead.created_at)


@router.get("/me/requests", response_model=Page[MyRequestOut])
async def my_requests(
    service: Service,
    principal: Annotated[Principal, Depends(require_user)],
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[MyRequestOut]:
    """The logged-in user's own requests, with the status updated by the agency."""
    return await service.list_my_requests(uuid.UUID(principal.subject), params)
