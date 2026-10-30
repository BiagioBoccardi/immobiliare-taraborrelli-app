import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from py_common.events import Event

from app.models.lead import Lead
from app.models.omi import OmiImport, OmiQuote, OmiZone
from app.schemas.lead import LeadFilters
from app.services.listing_prices import ListingStats


class FakeLeadRepository:
    def __init__(self, leads: list[Lead] | None = None) -> None:
        self.leads: dict[uuid.UUID, Lead] = {lead.id: lead for lead in leads or []}
        self.commits = 0

    async def add(self, lead: Lead) -> Lead:
        self.leads[lead.id] = lead
        return lead

    async def get(self, lead_id: uuid.UUID) -> Lead | None:
        return self.leads.get(lead_id)

    async def list(
        self, filters: LeadFilters, now: datetime, offset: int, limit: int
    ) -> tuple[list[Lead], int]:
        items = [
            lead
            for lead in self.leads.values()
            if (filters.status is None or lead.status == filters.status)
            and (filters.kind is None or lead.kind == filters.kind)
        ]
        return items[offset : offset + limit], len(items)

    async def delete(self, lead: Lead) -> None:
        del self.leads[lead.id]

    async def list_for_user(
        self, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[Sequence[Lead], int]:
        items = [lead for lead in self.leads.values() if lead.user_id == user_id]
        return items[offset : offset + limit], len(items)

    async def delete_for_user(self, user_id: uuid.UUID) -> int:
        doomed = [lead_id for lead_id, lead in self.leads.items() if lead.user_id == user_id]
        for lead_id in doomed:
            del self.leads[lead_id]
        return len(doomed)

    async def commit(self) -> None:
        self.commits += 1


class FailingPublisher:
    async def publish(self, event: Event[Any]) -> None:
        raise ConnectionError("broker down")


class FakeOmiRepository:
    def __init__(self) -> None:
        self.imports: list[OmiImport] = []
        self.quotes: list[OmiQuote] = []
        self.zones: list[OmiZone] = []

    async def replace_all(
        self, record: OmiImport, quotes: Sequence[OmiQuote], zones: Sequence[OmiZone]
    ) -> None:
        self.imports.append(record)
        self.quotes = list(quotes)
        self.zones = list(zones)

    async def latest_import(self) -> OmiImport | None:
        return self.imports[-1] if self.imports else None

    async def zones_around(self, longitude: float, latitude: float) -> Sequence[OmiZone]:
        return [
            z
            for z in self.zones
            if z.min_lon <= longitude <= z.max_lon and z.min_lat <= latitude <= z.max_lat
        ]

    async def quotes_of_zone(self, municipality_code: str, zone_code: str) -> Sequence[OmiQuote]:
        return [
            q
            for q in self.quotes
            if q.municipality_code == municipality_code and q.zone_code == zone_code
        ]


class RecordingNotifier:
    """Remembers the leads the agency was notified about."""

    def __init__(self) -> None:
        self.notified: list[Lead] = []

    async def new_lead(self, lead: Lead) -> None:
        self.notified.append(lead)


class FailingNotifier:
    async def new_lead(self, lead: Lead) -> None:
        raise ConnectionError("SMTP server unreachable")


class RecordingEmailSender:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, email: Any) -> None:
        self.sent.append(email)


class FakeListingPrices:
    """€/m² of the agency's listings without calling the property service."""

    def __init__(self, stats: ListingStats | None = None) -> None:
        self.result = stats
        self.calls: list[tuple[str, str]] = []

    async def stats(self, municipality: str, property_type: str) -> ListingStats | None:
        self.calls.append((municipality, property_type))
        return self.result
