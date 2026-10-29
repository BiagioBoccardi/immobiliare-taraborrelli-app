from fastapi import FastAPI
from httpx import AsyncClient

from app.core.dependencies import get_storage
from app.storage.cloudinary import CloudinaryCredentials, CloudinaryMediaStorage

URL = "/api/v1/property/admin/media/transfer-signatures"
BODY = {"action": "upload", "public_ids": ["trasferimento/TR00013/0.jpg"]}


def _use_cloudinary(app: FastAPI) -> None:
    storage = CloudinaryMediaStorage(
        CloudinaryCredentials(cloud_name="agenzia", api_key="123", api_secret="segreto")
    )
    app.dependency_overrides[get_storage] = lambda: storage


async def test_transfer_signatures_as_staff_return_one_per_photo(
    app: FastAPI, client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    _use_cloudinary(app)

    response = await client.post(URL, json=BODY, headers=staff_headers)

    assert response.status_code == 200
    assert [i["public_id"] for i in response.json()["items"]] == ["trasferimento/TR00013/0"]


async def test_transfer_signatures_outside_the_folder_return_422(
    app: FastAPI, client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    _use_cloudinary(app)
    body = {"action": "upload", "public_ids": ["properties/x/y.jpg"]}

    response = await client.post(URL, json=body, headers=staff_headers)

    assert response.status_code == 422


async def test_transfer_signatures_without_token_return_401(client: AsyncClient) -> None:
    response = await client.post(URL, json=BODY)

    assert response.status_code == 401


async def test_transfer_signatures_as_customer_return_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(URL, json=BODY, headers=user_headers)

    assert response.status_code == 403


async def test_transfer_signatures_without_cloudinary_return_409(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(URL, json=BODY, headers=staff_headers)

    assert response.status_code == 409
    assert response.json()["code"] == "transfer_unavailable"
