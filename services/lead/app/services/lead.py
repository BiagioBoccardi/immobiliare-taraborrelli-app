import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import Event, EventPublisher
from py_common.events.lead import (
    LeadConsentGivenV1,
    OwnerRequestReceivedV1,
    ValuationRequestedV1,
)
from py_common.pagination import Page, PageParams

from app.models.enums import LeadKind, LeadStatus
from app.models.lead import Lead
from app.repositories.lead import LeadRepository
from app.schemas.lead import (
    LeadFilters,
    LeadOut,
    LeadUpdate,
    OwnerRequestCreate,
    ValuationCreate,
    ValuationDetails,
)
from app.services.priority import priority_for
from app.services.tokens import hash_token, new_token, token_matches

logger = logging.getLogger(__name__)

PRODUCER = "lead"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CreatedValuation:
    lead: Lead
    completion_token: str
    completion_expires_at: datetime


class LeadService:
    def __init__(
        self,
        repository: LeadRepository,
        publisher: EventPublisher,
        completion_window: timedelta,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._repo = repository
        self._publisher = publisher
        self._completion_window = completion_window
        self._clock = clock

    async def create_valuation(self, data: ValuationCreate) -> CreatedValuation:
        now = self._clock()
        token = new_token()
        lead = Lead(
            id=uuid.uuid4(),
            kind=LeadKind.VALUATION,
            status=LeadStatus.NEW,
            priority=priority_for(data.intention),
            intention=data.intention,
            full_name=data.full_name,
            phone=data.phone,
            municipality=data.municipality,
            property_type=data.property_type,
            surface_sqm=data.surface_sqm,
            rooms=data.rooms,
            condition=data.condition,
            details={},
            completion_token_hash=hash_token(token),
            contact_consent_at=now,
            privacy_policy_version=data.consent.privacy_policy_version,
            marketing_consent=data.consent.marketing_accepted,
            created_at=now,
            updated_at=now,
        )
        await self._repo.add(lead)
        await self._repo.commit()
        await self._emit(
            ValuationRequestedV1(
                lead_id=lead.id,
                priority=lead.priority.value,
                municipality=lead.municipality,
                property_type=lead.property_type.value,
            )
        )
        await self._emit_consent(lead)
        return CreatedValuation(lead, token, now + self._completion_window)

    async def complete_valuation(
        self, lead_id: uuid.UUID, token: str, details: ValuationDetails
    ) -> None:
        lead = await self._repo.get(lead_id)
        # Same response for unknown lead and wrong token, so ids cannot be probed.
        if (
            lead is None
            or lead.kind is not LeadKind.VALUATION
            or not token_matches(token, lead.completion_token_hash)
        ):
            raise NotFoundError("Valuation not found")
        if self._clock() > lead.created_at + self._completion_window:
            raise ConflictError(
                "The time to complete this valuation has expired",
                code="completion_window_expired",
            )
        payload = details.model_dump(mode="json", exclude_none=True, exclude={"email"})
        lead.details = {**lead.details, **payload}
        if details.email is not None:
            lead.email = details.email
        lead.updated_at = self._clock()
        await self._repo.commit()

    async def create_owner_request(self, data: OwnerRequestCreate) -> Lead:
        now = self._clock()
        lead = Lead(
            id=uuid.uuid4(),
            kind=LeadKind(data.kind),
            status=LeadStatus.NEW,
            priority=priority_for(data.intention),
            intention=data.intention,
            full_name=data.full_name,
            phone=data.phone,
            municipality=data.municipality,
            property_type=data.property_type,
            surface_sqm=data.surface_sqm,
            rooms=data.rooms,
            message=data.message,
            details={},
            contact_consent_at=now,
            privacy_policy_version=data.consent.privacy_policy_version,
            marketing_consent=data.consent.marketing_accepted,
            created_at=now,
            updated_at=now,
        )
        await self._repo.add(lead)
        await self._repo.commit()
        kind = "sell" if lead.kind is LeadKind.SELL else "rent"
        await self._emit(
            OwnerRequestReceivedV1(
                lead_id=lead.id,
                kind=kind,
                priority=lead.priority.value,
                municipality=lead.municipality,
                property_type=lead.property_type.value,
            )
        )
        await self._emit_consent(lead)
        return lead

    async def list_leads(self, filters: LeadFilters, params: PageParams) -> Page[LeadOut]:
        leads, total = await self._repo.list(filters, self._clock(), params.offset, params.size)
        return Page[LeadOut](
            items=[LeadOut.model_validate(lead) for lead in leads],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def get_lead(self, lead_id: uuid.UUID) -> Lead:
        lead = await self._repo.get(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    async def update_lead(self, lead_id: uuid.UUID, changes: LeadUpdate) -> Lead:
        lead = await self.get_lead(lead_id)
        for field, value in changes.model_dump(exclude_unset=True).items():
            if field in {"status", "priority"} and value is None:
                raise AppError(f"{field} cannot be empty", code="invalid_update")
            setattr(lead, field, value)
        lead.updated_at = self._clock()
        await self._repo.commit()
        return lead

    async def delete_lead(self, lead_id: uuid.UUID) -> None:
        """GDPR erasure: removes the lead and all the personal data it contains."""
        lead = await self.get_lead(lead_id)
        await self._repo.delete(lead)
        await self._repo.commit()

    async def _emit_consent(self, lead: Lead) -> None:
        """Consents are stored in the auth registry (date, policy version, purpose)."""
        purposes: tuple[Literal["contact", "marketing"], ...] = (
            ("contact", "marketing") if lead.marketing_consent else ("contact",)
        )
        await self._emit(
            LeadConsentGivenV1(
                lead_id=lead.id,
                policy_version=lead.privacy_policy_version,
                purposes=purposes,
                given_at=lead.contact_consent_at,
            )
        )

    async def _emit(self, payload: Any) -> None:
        # The lead is already stored: a broker failure must not lose the owner's request.
        try:
            await self._publisher.publish(Event.wrap(payload, producer=PRODUCER))
        except Exception:
            logger.exception("failed to publish %s", payload.event_type)
