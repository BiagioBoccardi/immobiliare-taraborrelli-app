from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.core.config import Settings
from app.models.property import Property
from app.services.spreadsheet import read_spreadsheet
from tests.factories import import_row, property_payload, spreadsheet_bytes

Store = Callable[..., Awaitable[Property]]
BASE = "/api/v1/property/admin/properties"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload(data: bytes, name: str = "export.xlsx") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, data, XLSX)}


async def test_preview_import_as_staff_returns_rows_and_totals(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    data = spreadsheet_bytes([import_row(Riferimento="RS-1"), import_row(Prezzo="boh")])

    response = await client.post(
        f"{BASE}/import/preview", files=upload(data), headers=staff_headers
    )

    body = response.json()
    assert response.status_code == 200
    assert body["totals"] == {"create": 1, "update": 0, "invalid": 1}
    assert body["rows"][1]["row"] == 3
    assert body["rows"][1]["errors"][0]["code"] == "invalid_number"


async def test_preview_import_does_not_save_anything(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    await client.post(
        f"{BASE}/import/preview",
        files=upload(spreadsheet_bytes([import_row()])),
        headers=staff_headers,
    )

    listed = await client.get(BASE, headers=staff_headers)

    assert listed.json()["total"] == 0


async def test_run_import_creates_drafts_and_updates_existing(
    client: AsyncClient, staff_headers: dict[str, str], store: Store
) -> None:
    await store(external_ref="RS-1", price=150_000)
    data = spreadsheet_bytes(
        [import_row(Riferimento="RS-1", Prezzo=145_000), import_row(Riferimento="RS-2")]
    )

    response = await client.post(f"{BASE}/import", files=upload(data), headers=staff_headers)

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 1, "skipped": 0}
    listed = (await client.get(BASE, headers=staff_headers)).json()["items"]
    by_ref = {item["external_ref"]: item for item in listed}
    assert by_ref["RS-1"]["price"] == 145_000
    assert by_ref["RS-2"]["status"] == "draft"


async def test_run_import_twice_does_not_duplicate_listings(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    data = spreadsheet_bytes([import_row(Riferimento="RS-7")])
    await client.post(f"{BASE}/import", files=upload(data), headers=staff_headers)

    second = await client.post(f"{BASE}/import", files=upload(data), headers=staff_headers)

    assert second.json() == {"created": 0, "updated": 1, "skipped": 0}
    assert (await client.get(BASE, headers=staff_headers)).json()["total"] == 1


async def test_import_csv_export_is_accepted(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    csv = (
        "Riferimento;Contratto;Tipologia;Prezzo;Superficie;Comune\n"
        "RS-1;Affitto;Bilocale;450;55;Chieti Scalo\n"
    ).encode("cp1252")

    response = await client.post(
        f"{BASE}/import",
        files={"file": ("export.csv", csv, "text/csv")},
        headers=staff_headers,
    )

    assert response.json() == {"created": 1, "updated": 0, "skipped": 0}


async def test_import_old_xls_returns_400_with_code(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    xls = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64

    response = await client.post(
        f"{BASE}/import/preview", files=upload(xls, "export.xls"), headers=staff_headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "xls_not_supported"


async def test_import_too_large_file_returns_400(
    client: AsyncClient, staff_headers: dict[str, str], settings: Settings
) -> None:
    settings.max_import_bytes = 100

    response = await client.post(
        f"{BASE}/import/preview", files=upload(b"x" * 101), headers=staff_headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "file_too_large"


async def test_import_without_file_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(f"{BASE}/import", headers=staff_headers)

    assert response.status_code == 422


async def test_import_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/import", files=upload(spreadsheet_bytes([import_row()])))

    assert response.status_code == 401


async def test_import_with_user_role_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{BASE}/import", files=upload(spreadsheet_bytes([import_row()])), headers=user_headers
    )

    assert response.status_code == 403


async def test_download_template_returns_excel_file(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/import/template", headers=staff_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX
    assert "attachment" in response.headers["content-disposition"]
    assert read_spreadsheet(response.content, max_rows=10).headers[0] == "Riferimento"


async def test_download_template_with_user_role_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/import/template", headers=user_headers)

    assert response.status_code == 403


async def test_create_with_taken_management_code_returns_409(
    client: AsyncClient, staff_headers: dict[str, str], store: Store
) -> None:
    await store(external_ref="RS-1")

    response = await client.post(
        BASE, json=property_payload(external_ref="RS-1"), headers=staff_headers
    )

    assert response.status_code == 409
    assert response.json()["code"] == "external_ref_taken"
