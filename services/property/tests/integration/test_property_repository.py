from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    Feature,
    PropertyStatus,
    PropertyType,
    SortOrder,
    TenantType,
)
from app.models.property import Property
from app.repositories.properties import SqlPropertyRepository
from app.schemas.property import AdminFilters, SearchFilters

Store = Callable[..., Awaitable[Property]]
NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


async def _search_ids(db_session: AsyncSession, **filters: Any) -> list[Any]:
    items, _ = await SqlPropertyRepository(db_session).search(
        SearchFilters.model_validate(filters), 0, 50
    )
    return [item.id for item in items]


async def test_search_returns_only_public_statuses(db_session: AsyncSession, store: Store) -> None:
    published = await store()
    reserved = await store(status=PropertyStatus.RESERVED)
    for hidden in (PropertyStatus.DRAFT, PropertyStatus.SOLD, PropertyStatus.ARCHIVED):
        await store(status=hidden)

    ids = await _search_ids(db_session)

    assert set(ids) == {published.id, reserved.id}


async def test_search_filters_by_contract_type_and_price(
    db_session: AsyncSession, store: Store
) -> None:
    match = await store(property_type=PropertyType.VILLA, price=300_000)
    await store(property_type=PropertyType.VILLA, price=500_000)
    await store(property_type=PropertyType.APARTMENT, price=300_000)
    await store(contract=Contract.RENT, property_type=PropertyType.VILLA, price=1_000)

    ids = await _search_ids(
        db_session,
        contract="sale",
        property_types=["villa", "house"],
        price_min=200_000,
        price_max=400_000,
    )

    assert ids == [match.id]


async def test_search_municipality_is_case_insensitive(
    db_session: AsyncSession, store: Store
) -> None:
    match = await store(municipality="Chieti Scalo")
    await store(municipality="Francavilla al Mare")

    ids = await _search_ids(db_session, municipality="chieti scalo")

    assert ids == [match.id]


async def test_search_requires_all_features(db_session: AsyncSession, store: Store) -> None:
    both = await store(features=[Feature.GARDEN.value, Feature.GARAGE.value])
    await store(features=[Feature.GARDEN.value])

    ids = await _search_ids(db_session, features=["garden", "garage"])

    assert ids == [both.id]


async def test_search_filters_by_rooms_surface_and_energy_class(
    db_session: AsyncSession, store: Store
) -> None:
    match = await store(rooms=4, surface_sqm=120, energy_class=EnergyClass.A2)
    await store(rooms=2, surface_sqm=120, energy_class=EnergyClass.A2)
    await store(rooms=4, surface_sqm=60, energy_class=EnergyClass.A2)
    await store(rooms=4, surface_sqm=120, energy_class=EnergyClass.G)

    ids = await _search_ids(db_session, rooms_min=3, surface_min=100, energy_classes=["A2", "A1"])

    assert ids == [match.id]


async def test_search_student_rentals_by_tenant_accommodation_and_date(
    db_session: AsyncSession, store: Store
) -> None:
    rental = {"contract": Contract.RENT, "accommodation": Accommodation.SINGLE_ROOM}
    match = await store(
        **rental, tenant_types=[TenantType.STUDENTS.value], available_from=date(2026, 11, 1)
    )
    await store(**rental, tenant_types=[TenantType.WORKERS.value], available_from=None)
    await store(**rental, tenant_types=[TenantType.STUDENTS.value], available_from=date(2027, 2, 1))

    ids = await _search_ids(
        db_session,
        contract="rent",
        tenant_type="students",
        accommodation="single_room",
        available_by="2026-12-01",
    )

    assert ids == [match.id]


async def test_search_by_map_viewport(db_session: AsyncSession, store: Store) -> None:
    inside = await store(latitude=Decimal("42.35"), longitude=Decimal("14.16"))
    await store(latitude=Decimal("41.90"), longitude=Decimal("12.49"))
    await store(latitude=None, longitude=None)

    ids = await _search_ids(
        db_session, min_lat="42.30", max_lat="42.40", min_lng="14.10", max_lng="14.20"
    )

    assert ids == [inside.id]


async def test_search_sorts_by_price_and_paginates(db_session: AsyncSession, store: Store) -> None:
    for price in (300_000, 100_000, 200_000):
        await store(price=price)
    repo = SqlPropertyRepository(db_session)

    items, total = await repo.search(SearchFilters(sort=SortOrder.PRICE_ASC), offset=1, limit=1)

    assert total == 3
    assert [item.price for item in items] == [200_000]


async def test_search_newest_first(db_session: AsyncSession, store: Store) -> None:
    old = await store(published_at=NOW - timedelta(days=3))
    new = await store(published_at=NOW)

    ids = await _search_ids(db_session, sort="newest")

    assert ids == [new.id, old.id]


async def test_list_admin_finds_by_reference_and_address(
    db_session: AsyncSession, store: Store
) -> None:
    item = await store(status=PropertyStatus.DRAFT, address="Via dei Vestini 10")
    await store(address="Corso Marrucino 5")
    repo = SqlPropertyRepository(db_session)

    by_reference, _ = await repo.list_admin(AdminFilters(q=item.reference.lower()), 0, 10)
    by_address, _ = await repo.list_admin(AdminFilters(q="vestini"), 0, 10)

    assert [i.id for i in by_reference] == [item.id]
    assert [i.id for i in by_address] == [item.id]


async def test_list_admin_finds_by_exact_management_code(
    db_session: AsyncSession, store: Store
) -> None:
    item = await store(external_ref="75")
    await store(external_ref="175")
    repo = SqlPropertyRepository(db_session)

    items, total = await repo.list_admin(AdminFilters(q=" 75 "), 0, 10)

    assert total == 1
    assert items[0].id == item.id


async def test_list_admin_filters_by_status(db_session: AsyncSession, store: Store) -> None:
    draft = await store(status=PropertyStatus.DRAFT)
    await store()

    items, total = await SqlPropertyRepository(db_session).list_admin(
        AdminFilters(status=PropertyStatus.DRAFT), 0, 10
    )

    assert total == 1
    assert items[0].id == draft.id


async def test_list_sold_orders_by_closing_date(db_session: AsyncSession, store: Store) -> None:
    older = await store(status=PropertyStatus.SOLD, closed_at=NOW - timedelta(days=30))
    newer = await store(status=PropertyStatus.SOLD, closed_at=NOW)
    await store(status=PropertyStatus.RENTED, closed_at=NOW)

    items, total = await SqlPropertyRepository(db_session).list_sold(0, 10)

    assert total == 2
    assert [i.id for i in items] == [newer.id, older.id]


async def test_add_assigns_sequential_reference(db_session: AsyncSession, store: Store) -> None:
    first = await store()
    second = await store()

    assert second.number == first.number + 1
    assert first.reference == f"TR{first.number:05d}"


async def test_deleting_property_deletes_its_photos(db_session: AsyncSession, store: Store) -> None:
    item = await store(photos=2, status=PropertyStatus.DRAFT)
    repo = SqlPropertyRepository(db_session)

    await repo.delete(item)

    from sqlalchemy import func, select

    from app.models.property import Photo

    assert await db_session.scalar(select(func.count()).select_from(Photo)) == 0


async def test_find_by_external_refs_returns_matching_listings(
    db_session: AsyncSession, store: Any
) -> None:
    first = await store(external_ref="RS-1")
    await store(external_ref="RS-2")
    await store(external_ref=None)
    repo = SqlPropertyRepository(db_session)

    found = await repo.find_by_external_refs(["RS-1", "RS-404"])

    assert list(found) == ["RS-1"]
    assert found["RS-1"].id == first.id


async def test_find_by_external_refs_with_no_refs_returns_empty(db_session: AsyncSession) -> None:
    repo = SqlPropertyRepository(db_session)

    assert await repo.find_by_external_refs([]) == {}
