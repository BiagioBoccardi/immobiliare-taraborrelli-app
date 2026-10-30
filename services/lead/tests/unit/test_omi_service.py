from datetime import UTC, datetime

import pytest
from py_common.errors import NotFoundError

from app.services.omi import OmiImportError, OmiService, UploadedFile
from tests.factories import OMI_ROWS, omi_kml, omi_values_csv, omi_zones_csv
from tests.unit.fakes import FakeOmiRepository

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


def _service(repo: FakeOmiRepository) -> OmiService:
    return OmiService(repo, clock=lambda: NOW)


async def _import(service: OmiService, kml: bytes | None = None) -> None:
    await service.import_files(
        UploadedFile("valori.csv", omi_values_csv()),
        UploadedFile("zone.csv", omi_zones_csv()),
        [UploadedFile("chieti.kml", kml or omi_kml())],
    )


async def test_import_files_stores_quotes_zones_and_summary() -> None:
    repo = FakeOmiRepository()

    result = await _service(repo).import_files(
        UploadedFile("valori.csv", omi_values_csv()),
        UploadedFile("zone.csv", omi_zones_csv()),
        [UploadedFile("chieti.kml", omi_kml())],
    )

    assert (result.semester, result.quotes, result.zones) == ("2026/1", 5, 2)
    assert result.municipalities == ["Chieti"]
    assert result.warnings == []
    assert repo.quotes[0].zone_description == "CENTRO STORICO"


async def test_import_files_warns_about_zones_without_perimeter() -> None:
    repo = FakeOmiRepository()

    result = await _service(repo).import_files(
        UploadedFile("valori.csv", omi_values_csv()),
        None,
        [UploadedFile("chieti.kml", omi_kml({"B1": (14.15, 42.34, 14.17, 42.36)}))],
    )

    assert [(w.code, w.examples) for w in result.warnings] == [
        ("zone_without_perimeter", ["Chieti D1"])
    ]


async def test_import_files_warns_about_perimeters_without_quotes() -> None:
    squares = {"B1": (14.15, 42.34, 14.17, 42.36), "Z9": (14.3, 42.3, 14.4, 42.4)}

    result = await _service(FakeOmiRepository()).import_files(
        UploadedFile("valori.csv", omi_values_csv(OMI_ROWS[:1])),
        None,
        [UploadedFile("chieti.kml", omi_kml(squares))],
    )

    assert {w.code for w in result.warnings} == {"perimeter_without_quotes"}
    assert result.zones == 1


async def test_import_files_without_residential_quotes_raises() -> None:
    with pytest.raises(OmiImportError) as error:
        await _service(FakeOmiRepository()).import_files(
            UploadedFile("valori.csv", omi_values_csv(OMI_ROWS[4:5])),
            None,
            [UploadedFile("chieti.kml", omi_kml())],
        )

    assert error.value.code == "omi_no_quotes"


async def test_import_files_with_wrong_file_names_the_file() -> None:
    with pytest.raises(OmiImportError) as error:
        await _service(FakeOmiRepository()).import_files(
            UploadedFile("valori.csv", omi_values_csv()),
            None,
            [UploadedFile("foto.jpg", b"\xff\xd8\xff")],
        )

    assert (error.value.code, error.value.details) == ("omi_invalid_file", {"file": "foto.jpg"})


async def test_import_files_without_perimeters_raises() -> None:
    empty = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>'

    with pytest.raises(OmiImportError) as error:
        await _service(FakeOmiRepository()).import_files(
            UploadedFile("valori.csv", omi_values_csv()), None, [UploadedFile("v.kml", empty)]
        )

    assert error.value.code == "omi_no_perimeters"


async def test_current_before_any_import_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _service(FakeOmiRepository()).current()


async def test_find_zone_returns_zone_and_quotes_of_the_point() -> None:
    service = _service(FakeOmiRepository())
    await _import(service)

    match = await service.find_zone(14.16, 42.35)

    assert match is not None
    assert (match.municipality, match.zone_code, match.zone_description) == (
        "Chieti",
        "B1",
        "CENTRO STORICO",
    )
    assert match.semester == "2026/1"
    assert len(match.quotes) == 4


async def test_find_zone_outside_every_zone_returns_none() -> None:
    service = _service(FakeOmiRepository())
    await _import(service)

    assert await service.find_zone(13.0, 41.0) is None


async def test_find_zone_with_overlapping_zones_picks_the_smallest() -> None:
    service = _service(FakeOmiRepository())
    await _import(
        service, omi_kml({"D1": (14.0, 42.0, 14.5, 42.5), "B1": (14.15, 42.34, 14.17, 42.36)})
    )

    match = await service.find_zone(14.16, 42.35)

    assert match is not None and match.zone_code == "B1"
