import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import Event, EventPublisher
from py_common.events.lead import (
    CallbackRequestedV1,
    LeadConsentGivenV1,
    OwnerRequestReceivedV1,
    ValuationRequestedV1,
)
from py_common.pagination import Page, PageParams

from app.models.enums import BuildingWorks, CadastralCategory, LeadKind, LeadPriority, LeadStatus
from app.models.lead import Lead
from app.repositories.lead import LeadRepository
from app.schemas.lead import (
    CallbackRequestCreate,
    EstimateOut,
    EstimateUnavailable,
    LeadFilters,
    LeadOut,
    LeadUpdate,
    MyRequestOut,
    OwnerRequestCreate,
    ValuationCreate,
    ValuationDetails,
)
from app.services.estimate import SUPPORTED_TYPES, EstimateInput, estimate_value
from app.services.notifications import NoStaffNotifier, StaffNotifier
from app.services.omi import OmiService
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
    estimate: EstimateOut | None = None
    estimate_unavailable: EstimateUnavailable | None = None


class LeadService:
    def __init__(
        self,
        repository: LeadRepository,
        publisher: EventPublisher,
        completion_window: timedelta,
        clock: Callable[[], datetime] = utcnow,
        omi: OmiService | None = None,
        notifier: StaffNotifier | None = None,
    ) -> None:
        self._repo = repository
        self._publisher = publisher
        self._completion_window = completion_window
        self._clock = clock
        self._omi = omi
        self._notifier = notifier or NoStaffNotifier()

    async def create_valuation(
        self, data: ValuationCreate, user_id: uuid.UUID | None = None
    ) -> CreatedValuation:
        now = self._clock()
        token = new_token()
        estimate, unavailable = await self._estimate(data)
        details = data.model_dump(
            mode="json",
            exclude_none=True,
            include={
                "address",
                "latitude",
                "longitude",
                "cadastral_category",
                "building_works",
                "floor",
                "has_elevator",
            },
        )
        if estimate is not None:
            # Kept with the lead: the agent sees what the owner was shown.
            details["estimate"] = {
                **estimate.model_dump(mode="json"),
                "computed_at": now.isoformat(),
            }
        lead = Lead(
            id=uuid.uuid4(),
            kind=LeadKind.VALUATION,
            status=LeadStatus.NEW,
            user_id=user_id,
            priority=priority_for(data.intention),
            intention=data.intention,
            full_name=data.full_name,
            phone=data.phone,
            municipality=data.municipality,
            property_type=data.property_type,
            surface_sqm=data.surface_sqm,
            rooms=data.rooms,
            condition=data.condition,
            details=details,
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
                municipality=data.municipality,
                property_type=data.property_type.value,
            )
        )
        await self._emit_consent(lead)
        await self._notify_staff(lead)
        return CreatedValuation(lead, token, now + self._completion_window, estimate, unavailable)

    async def _estimate(
        self, data: ValuationCreate
    ) -> tuple[EstimateOut | None, EstimateUnavailable | None]:
        """Indicative range from the OMI zone of the address, when it can be computed."""
        if self._omi is None or data.latitude is None or data.longitude is None:
            return None, "no_location"
        if data.property_type not in SUPPORTED_TYPES:
            return None, "type_not_supported"
        zone = await self._omi.find_zone(data.longitude, data.latitude)
        if zone is None:
            return None, "outside_zones"
        value = estimate_value(
            EstimateInput(
                property_type=data.property_type,
                surface_sqm=data.surface_sqm,
                condition=data.condition,
                cadastral_category=data.cadastral_category or CadastralCategory.UNKNOWN,
                building_works=data.building_works or BuildingWorks.UNKNOWN,
                floor=data.floor,
                has_elevator=data.has_elevator,
            ),
            zone.quotes,
        )
        if value is None:
            return None, "no_quotes"
        return (
            EstimateOut(
                min_value=value.min_value,
                max_value=value.max_value,
                min_per_sqm=value.min_per_sqm,
                max_per_sqm=value.max_per_sqm,
                municipality=zone.municipality,
                zone_code=zone.zone_code,
                zone_description=zone.zone_description,
                semester=zone.semester,
            ),
            None,
        )

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

    async def create_owner_request(
        self, data: OwnerRequestCreate, user_id: uuid.UUID | None = None
    ) -> Lead:
        now = self._clock()
        lead = Lead(
            id=uuid.uuid4(),
            kind=LeadKind(data.kind),
            status=LeadStatus.NEW,
            user_id=user_id,
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
                municipality=data.municipality,
                property_type=data.property_type.value,
            )
        )
        await self._emit_consent(lead)
        await self._notify_staff(lead)
        return lead

    async def create_callback_request(
        self, data: CallbackRequestCreate, user_id: uuid.UUID | None = None
    ) -> Lead:
        """The website promises a call back by the next working day, so the request is
        due for contact as soon as it arrives and shows up in "Da ricontattare"."""
        now = self._clock()
        lead = Lead(
            id=uuid.uuid4(),
            kind=LeadKind.CALLBACK,
            status=LeadStatus.NEW,
            user_id=user_id,
            priority=LeadPriority.MEDIUM,
            intention=None,
            full_name=f"{data.first_name} {data.last_name}",
            phone=data.phone,
            email=data.email,
            municipality=None,
            property_type=None,
            message=data.message or None,
            details={"preferred_time": data.preferred_time.value, "source": "website"},
            contact_consent_at=now,
            privacy_policy_version=data.consent.privacy_policy_version,
            marketing_consent=data.consent.marketing_accepted,
            next_contact_at=now,
            created_at=now,
            updated_at=now,
        )
        await self._repo.add(lead)
        await self._repo.commit()
        await self._emit(
            CallbackRequestedV1(
                lead_id=lead.id,
                priority=lead.priority.value,
                preferred_time=data.preferred_time.value,
            )
        )
        await self._emit_consent(lead)
        await self._notify_staff(lead)
        return lead

    async def list_leads(self, filters: LeadFilters, params: PageParams) -> Page[LeadOut]:
        leads, total = await self._repo.list(filters, self._clock(), params.offset, params.size)
        return Page[LeadOut](
            items=[LeadOut.model_validate(lead) for lead in leads],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def list_my_requests(self, user_id: uuid.UUID, params: PageParams) -> Page[MyRequestOut]:
        leads, total = await self._repo.list_for_user(user_id, params.offset, params.size)
        return Page[MyRequestOut](
            items=[MyRequestOut.model_validate(lead) for lead in leads],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def delete_user_requests(self, user_id: uuid.UUID) -> int:
        """GDPR erasure after `auth.user_deleted`. Idempotent: a second call deletes nothing."""
        deleted = await self._repo.delete_for_user(user_id)
        await self._repo.commit()
        return deleted

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

    async def _notify_staff(self, lead: Lead) -> None:
        # Sent before answering: on Cloud Run work after the response may never run.
        # The request is already stored, so a failed email must not fail the form.
        try:
            await self._notifier.new_lead(lead)
        except Exception:
            logger.exception("failed to notify the agency of a new lead")

    async def _emit(self, payload: Any) -> None:
        # The lead is already stored: a broker failure must not lose the owner's request.
        try:
            await self._publisher.publish(Event.wrap(payload, producer=PRODUCER))
        except Exception:
            logger.exception("failed to publish %s", payload.event_type)
