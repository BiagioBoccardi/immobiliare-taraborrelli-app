from fastapi import FastAPI
from httpx import AsyncClient

from app.core.dependencies import get_storage
from app.storage.cloudinary import CloudinaryCredentials, CloudinaryMediaStorage

SIGNATURE_URL = "/api/v1/property/admin/media/transfer-signature"
CLEANUP_URL = "/api/v1/property/admin/media/transfer-cleanup"


def _use_cloudinary(app: FastAPI) -> None:
    def admin_api(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        return 200, b'{"deleted": {"trasferimento/x": "deleted"}, "partial": false}'

    storage = CloudinaryMediaStorage(
        CloudinaryCredentials(cloud_name="agenzia", api_key="123", api_secret="segreto"),
        http_request=admin_api,
    )
    app.dependency_overrides[get_storage] = lambda: storage


async def test_transfer_signature_as_staff_returns_the_folder(
    app: FastAPI, client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    _use_cloudinary(app)

    response = await client.post(SIGNATURE_URL, headers=staff_headers)

    assert response.status_code == 200
    assert response.json()["folder"] == "trasferimento"


async def test_transfer_cleanup_as_staff_returns_deleted_count(
    app: FastAPI, client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    _use_cloudinary(app)

    response = await client.post(CLEANUP_URL, headers=staff_headers)

    assert response.json() == {"deleted": 1}


async def test_transfer_signature_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(SIGNATURE_URL)

    assert response.status_code == 401


async def test_transfer_signature_as_customer_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(SIGNATURE_URL, headers=user_headers)

    assert response.status_code == 403


async def test_transfer_signature_without_cloudinary_returns_409(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(SIGNATURE_URL, headers=staff_headers)

    assert response.status_code == 409
    assert response.json()["code"] == "transfer_unavailable"


async def test_transfer_cleanup_with_another_folder_in_body_cleans_only_transfer(
    app: FastAPI, client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    _use_cloudinary(app)

    response = await client.post(CLEANUP_URL, json={"folder": "properties"}, headers=staff_headers)

    assert response.json() == {"deleted": 1}
