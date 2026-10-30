from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OmiState, OmiType
from app.models.omi import OmiImport, OmiQuote, OmiZone
from app.repositories.omi import SqlOmiRepository


def _zone(code: str, west: float, east: float) -> OmiZone:
    ring = [[west, 42.0], [east, 42.0], [east, 43.0], [west, 43.0]]
    return OmiZone(
        municipality_code="C632",
        zone_code=code,
        polygons=[[ring]],
        min_lon=west,
        min_lat=42.0,
        max_lon=east,
        max_lat=43.0,
    )


def _quote(zone: str) -> OmiQuote:
    return OmiQuote(
        municipality_code="C632",
        municipality="Chieti",
        zone_code=zone,
        omi_type=OmiType.CIVIL,
        state=OmiState.NORMAL,
        prevalent=True,
        sale_min=1000,
        sale_max=1400,
    )


def _record(semester: str, day: int) -> OmiImport:
    return OmiImport(
        semester=semester,
        quotes=1,
        zones=1,
        municipalities=["Chieti"],
        imported_at=datetime(2026, 10, day, tzinfo=UTC),
    )


async def test_replace_all_removes_the_previous_import(db_session: AsyncSession) -> None:
    repo = SqlOmiRepository(db_session)
    await repo.replace_all(_record("2025/2", 1), [_quote("B1")], [_zone("B1", 14.0, 14.1)])

    await repo.replace_all(_record("2026/1", 2), [_quote("D1")], [_zone("D1", 14.1, 14.2)])

    latest = await repo.latest_import()
    assert latest is not None and latest.semester == "2026/1"
    assert await repo.quotes_of_zone("C632", "B1") == []
    assert [q.zone_code for q in await repo.quotes_of_zone("C632", "D1")] == ["D1"]


async def test_zones_around_filters_by_bounding_box(db_session: AsyncSession) -> None:
    repo = SqlOmiRepository(db_session)
    await repo.replace_all(
        _record("2026/1", 3), [], [_zone("B1", 14.0, 14.1), _zone("D1", 14.1, 14.2)]
    )

    zones = await repo.zones_around(14.05, 42.5)

    assert [z.zone_code for z in zones] == ["B1"]
