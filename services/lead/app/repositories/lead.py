import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadPriority
from app.models.lead import Lead
from app.schemas.lead import LeadFilters

_PRIORITY_RANK = case(
    {LeadPriority.HIGH: 0, LeadPriority.MEDIUM: 1, LeadPriority.LOW: 2},
    value=Lead.priority,
)


class LeadRepository(Protocol):
    async def add(self, lead: Lead) -> Lead: ...

    async def get(self, lead_id: uuid.UUID) -> Lead | None: ...

    async def list(
        self, filters: LeadFilters, now: datetime, offset: int, limit: int
    ) -> tuple[list[Lead], int]: ...

    async def delete(self, lead: Lead) -> None: ...

    async def commit(self) -> None: ...


class SqlLeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, lead: Lead) -> Lead:
        self._session.add(lead)
        await self._session.flush()
        return lead

    async def get(self, lead_id: uuid.UUID) -> Lead | None:
        return await self._session.get(Lead, lead_id)

    async def list(
        self, filters: LeadFilters, now: datetime, offset: int, limit: int
    ) -> tuple[list[Lead], int]:
        query = select(Lead)
        if filters.kind is not None:
            query = query.where(Lead.kind == filters.kind)
        if filters.status is not None:
            query = query.where(Lead.status == filters.status)
        if filters.priority is not None:
            query = query.where(Lead.priority == filters.priority)
        if filters.due_for_contact:
            query = query.where(Lead.next_contact_at <= now)

        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        ordering: tuple[Any, ...]
        if filters.due_for_contact:
            ordering = (Lead.next_contact_at.asc(), Lead.id)
        else:
            ordering = (_PRIORITY_RANK, Lead.created_at.desc(), Lead.id)
        rows = await self._session.scalars(query.order_by(*ordering).offset(offset).limit(limit))
        return list(rows), int(total or 0)

    async def delete(self, lead: Lead) -> None:
        await self._session.delete(lead)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
