import uuid
from collections.abc import Collection

from app.models.enums import PUBLIC_STATUSES, Contract, PropertyStatus
from app.models.property import Property
from app.schemas.property import AdminFilters, SearchFilters
from app.services.price_stats import Sample


class InMemoryStorage:
    def __init__(self, fail_on_put: bool = False) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_on_put = fail_on_put

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_on_put:
            raise ConnectionError("storage down")
        self.objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def public_url(self, key: str) -> str:
        return f"https://media.test/{key}"


class FakePropertyRepository:
    def __init__(self, items: list[Property] | None = None) -> None:
        self.items: dict[uuid.UUID, Property] = {item.id: item for item in items or []}
        self.commits = 0
        self.fail_on_commit = False
        self._next_number = 100

    async def add(self, item: Property) -> Property:
        self._next_number += 1
        item.number = self._next_number
        if "photos" not in item.__dict__:
            item.photos = []
        self.items[item.id] = item
        return item

    async def get(self, property_id: uuid.UUID) -> Property | None:
        return self.items.get(property_id)

    async def find_by_external_refs(self, refs: Collection[str]) -> dict[str, Property]:
        return {
            item.external_ref: item
            for item in self.items.values()
            if item.external_ref is not None and item.external_ref in refs
        }

    async def search(
        self, filters: SearchFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]:
        found = [
            i
            for i in self.items.values()
            if i.status in {PropertyStatus.PUBLISHED, PropertyStatus.RESERVED}
        ]
        return found[offset : offset + limit], len(found)

    async def list_admin(
        self, filters: AdminFilters, offset: int, limit: int
    ) -> tuple[list[Property], int]:
        found = list(self.items.values())
        return found[offset : offset + limit], len(found)

    async def list_sold(self, offset: int, limit: int) -> tuple[list[Property], int]:
        found = [i for i in self.items.values() if i.status is PropertyStatus.SOLD]
        return found[offset : offset + limit], len(found)

    async def sale_price_samples(self) -> list[Sample]:
        return [
            Sample(i.municipality, i.property_type, i.price, i.surface_sqm or 0)
            for i in self.items.values()
            if i.contract is Contract.SALE
            and i.status in {*PUBLIC_STATUSES, PropertyStatus.SOLD}
            and (i.surface_sqm or 0) > 0
        ]

    async def delete(self, item: Property) -> None:
        del self.items[item.id]

    async def commit(self) -> None:
        if self.fail_on_commit:
            raise RuntimeError("database down")
        self.commits += 1
