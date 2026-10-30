from httpx import AsyncClient

from tests.factories import omi_kmz, omi_values_csv, omi_zones_csv

BASE = "/api/v1/lead/omi"


def _files(perimeter: bytes | None = None) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("quotes", ("QI_1_1_20261_VALORI.csv", omi_values_csv(), "text/csv")),
        ("zones", ("QI_1_1_20261_ZONE.csv", omi_zones_csv(), "text/csv")),
        ("perimeters", ("Provincia di CHIETI.kmz", perimeter or omi_kmz(), "application/zip")),
    ]


async def test_import_omi_as_staff_returns_summary(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, files=_files(), headers=staff_headers)

    body = response.json()
    assert response.status_code == 201
    assert (body["semester"], body["quotes"], body["zones"]) == ("2026/1", 5, 2)
    assert body["municipalities"] == ["Chieti"]


async def test_current_omi_after_import_returns_the_data_in_use(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    await client.post(BASE, files=_files(), headers=staff_headers)

    response = await client.get(BASE, headers=staff_headers)

    assert response.status_code == 200
    assert response.json()["zones"] == 2


async def test_current_omi_before_import_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(BASE, headers=staff_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "omi_not_loaded"


async def test_import_omi_with_invalid_perimeter_returns_422_with_file(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, files=_files(b"not a kml"), headers=staff_headers)

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "omi_invalid_file"
    assert body["details"] == {"file": "Provincia di CHIETI.kmz"}


async def test_import_omi_without_perimeters_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    files = _files()[:2]

    response = await client.post(BASE, files=files, headers=staff_headers)

    assert response.status_code == 422


async def test_import_omi_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(BASE, files=_files())

    assert response.status_code == 401


async def test_import_omi_as_app_user_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, files=_files(), headers=user_headers)

    assert response.status_code == 403
