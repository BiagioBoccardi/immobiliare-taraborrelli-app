import uuid
from datetime import datetime
from typing import Any

from py_common.events import Event

from app.models.lead import Lead
from app.schemas.lead import LeadFilters


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

    async def commit(self) -> None:
        self.commits += 1


class FailingPublisher:
    async def publish(self, event: Event[Any]) -> None:
        raise ConnectionError("broker down")
