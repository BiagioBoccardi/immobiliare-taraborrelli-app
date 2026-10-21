from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.models.enums import Contract, PropertyStatus
from app.models.property import Property

Store = Callable[..., Awaitable[Property]]
BASE = "/api/v1/property/admin/properties"


async def test_bulk_publish_with_draft_filter_publishes_ready_drafts(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    ready = await store(status=PropertyStatus.DRAFT, published_at=None)
    await store(status=PropertyStatus.DRAFT, photos=0)

    response = await client.post(
        f"{BASE}/bulk/publish", json={"status": "draft"}, headers=staff_headers
    )

    body = response.json()
    assert response.status_code == 200
    assert body["done"] == 1
    assert [s["reason"] for s in body["skipped"]] == ["photo_required"]
    detail = await client.get(f"{BASE}/{ready.id}", headers=staff_headers)
    assert detail.json()["status"] == "published"


async def test_bulk_delete_with_contract_filter_deletes_only_matching(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    await store(contract=Contract.RENT, price=500)
    kept = await store(contract=Contract.SALE)

    response = await client.post(
        f"{BASE}/bulk/delete", json={"contract": "rent"}, headers=staff_headers
    )

    assert response.json() == {"done": 1, "skipped": []}
    listed = (await client.get(BASE, headers=staff_headers)).json()
    assert [item["id"] for item in listed["items"]] == [str(kept.id)]


async def test_bulk_publish_with_unknown_status_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{BASE}/bulk/publish", json={"status": "boh"}, headers=staff_headers
    )

    assert response.status_code == 422


async def test_bulk_delete_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/bulk/delete", json={})

    assert response.status_code == 401


async def test_bulk_delete_with_user_role_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(f"{BASE}/bulk/delete", json={}, headers=user_headers)

    assert response.status_code == 403
