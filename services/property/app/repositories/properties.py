import uuid
from collections.abc import Collection
from typing import Any, Protocol

from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PUBLIC_STATUSES, PropertyStatus, SortOrder
from app.models.property import Property
from app.schemas.property import AdminFilters, SearchFilters


def _search_query(filters: SearchFilters) -> Select[Property]:
    query = select(Property).where(Property.status.in_(PUBLIC_STATUSES))
    if filters.contract is not None:
        query = query.where(Property.contract == filters.contract)
    if filters.property_types:
        query = query.where(Property.property_type.in_(filters.property_types))
    if filters.municipality:
        query = query.where(func.lower(Property.municipality) == filters.municipality.lower())
    if filters.zone:
        query = query.where(func.lower(Property.zone) == filters.zone.lower())
    if filters.price_min is not None:
        query = query.where(Property.price >= filters.price_min)
    if filters.price_max is not None:
        query = query.where(Property.price <= filters.price_max)
    if filters.surface_min is not None:
        query = query.where(Property.surface_sqm >= filters.surface_min)
    if filters.surface_max is not None:
        query = query.where(Property.surface_sqm <= filters.surface_max)
    if filters.rooms_min is not None:
        query = query.where(Property.rooms >= filters.rooms_min)
    if filters.bedrooms_min is not None:
        query = query.where(Property.bedrooms >= filters.bedrooms_min)
    if filters.bathrooms_min is not None:
        query = query.where(Property.bathrooms >= filters.bathrooms_min)
    if filters.features:
        query = query.where(Property.features.contains([f.value for f in filters.features]))
    if filters.energy_classes:
        query = query.where(Property.energy_class.in_(filters.energy_classes))
    if filters.featured is not None:
        query = query.where(Property.is_featured.is_(filters.featured))
    if filters.tenant_type is not None:
        query = query.where(Property.tenant_types.contains([filters.tenant_type.value]))
    if filters.accommodation is not None:
        query = query.where(Property.accommodation == filters.accommodation)
    if filters.available_by is not None:
        query = query.where(
            or_(Property.available_from.is_(None), Property.available_from <= filters.available_by)
        )
    if filters.min_lat is not None:
        query = query.where(
            Property.latitude.between(filters.min_lat, filters.max_lat),
            Property.longitude.between(filters.min_lng, filters.max_lng),
        )
    return query


_ORDERING: dict[SortOrder, tuple[Any, ...]] = {
    SortOrder.NEWEST: (Property.published_at.desc().nulls_last(), Property.id),
    SortOrder.PRICE_ASC: (Property.price.asc(), Property.id),
    SortOrder.PRICE_DESC: (Property.price.desc(), Property.id),
    SortOrder.SURFACE_DESC: (Property.surface_sqm.desc(), Property.id),
}


class PropertyRepository(Protocol):
    async def add(self, item: Property) -> Property: ...

    async def get(self, property_id: uuid.UUID) -> Property | None: ...

    async def find_by_external_refs(self, refs: Collection[str]) -> dict[str, Property]: ...

    async def search(
        self, filters: SearchFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]: ...

    async def list_admin(
        self, filters: AdminFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]: ...

    async def list_sold(self, offset: int, limit: int) -> tuple[list[Property], int]: ...

    async def delete(self, item: Property) -> None: ...

    async def commit(self) -> None: ...


class SqlPropertyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: Property) -> Property:
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item, attribute_names=["number", "photos"])
        return item

    async def get(self, property_id: uuid.UUID) -> Property | None:
        return await self._session.get(Property, property_id)

    async def find_by_external_refs(self, refs: Collection[str]) -> dict[str, Property]:
        if not refs:
            return {}
        rows = await self._session.scalars(
            select(Property).where(Property.external_ref.in_(list(refs)))
        )
        return {item.external_ref: item for item in rows if item.external_ref is not None}

    async def _page(
        self, query: Select[Property], ordering: tuple[Any, ...], offset: int, limit: int
    ) -> tuple[list[Property], int]:
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._session.scalars(query.order_by(*ordering).offset(offset).limit(limit))
        return list(rows), int(total or 0)

    async def search(
        self, filters: SearchFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]:
        return await self._page(_search_query(filters), _ORDERING[filters.sort], offset, limit)

    async def list_admin(
        self, filters: AdminFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]:
        query = select(Property)
        if filters.status is not None:
            query = query.where(Property.status == filters.status)
        if filters.contract is not None:
            query = query.where(Property.contract == filters.contract)
        if filters.q:
            term = f"%{filters.q.lower()}%"
            reference = func.concat("tr", func.lpad(cast(Property.number, String), 5, "0"))
            query = query.where(
                or_(
                    func.lower(Property.title).like(term),
                    func.lower(Property.municipality).like(term),
                    func.lower(Property.address).like(term),
                    reference.like(term),
                )
            )
        ordering = (Property.updated_at.desc(), Property.id)
        return await self._page(query, ordering, offset, limit)

    async def list_sold(self, offset: int, limit: int) -> tuple[list[Property], int]:
        query = select(Property).where(Property.status == PropertyStatus.SOLD)
        ordering = (Property.closed_at.desc().nulls_last(), Property.id)
        return await self._page(query, ordering, offset, limit)

    async def delete(self, item: Property) -> None:
        await self._session.delete(item)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
