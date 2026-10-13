import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from httpx import AsyncClient

from app.models.enums import PropertyStatus
from app.models.property import Property

Store = Callable[..., Awaitable[Property]]
BASE = "/api/v1/property"


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.json() == {"status": "ok"}


async def test_search_without_login_returns_paginated_cards(
    client: AsyncClient, store: Store
) -> None:
    for _ in range(3):
        await store()

    response = await client.get(f"{BASE}/properties", params={"size": 2})

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["cover_photo"]["url"].startswith("https://media.test/")


async def test_search_cards_hide_address_and_round_coordinates(
    client: AsyncClient, store: Store
) -> None:
    await store()

    response = await client.get(f"{BASE}/properties")

    card = response.json()["items"][0]
    assert "address" not in card
    assert card["coordinates"] == {"latitude": "42.351", "longitude": "14.168", "exact": False}


async def test_search_with_multiple_types_and_features(client: AsyncClient, store: Store) -> None:
    match = await store(features=["garden"], property_type="villa")
    await store(features=[], property_type="villa")

    response = await client.get(
        f"{BASE}/properties",
        params=[("property_type", "villa"), ("property_type", "house"), ("feature", "garden")],
    )

    assert [i["id"] for i in response.json()["items"]] == [str(match.id)]


async def test_search_with_unknown_type_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/properties", params={"property_type": "castle"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_search_with_partial_viewport_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/properties", params={"min_lat": 42.3})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_search_with_page_size_over_limit_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/properties", params={"size": 1000})

    assert response.status_code == 422


async def test_get_published_property_returns_detail_with_photos(
    client: AsyncClient, store: Store
) -> None:
    item = await store(photos=2)

    response = await client.get(f"{BASE}/properties/{item.id}")

    body = response.json()
    assert response.status_code == 200
    assert body["reference"] == item.reference
    assert len(body["photos"]) == 2
    assert "address" not in body


async def test_get_draft_property_returns_404(client: AsyncClient, store: Store) -> None:
    item = await store(status=PropertyStatus.DRAFT)

    response = await client.get(f"{BASE}/properties/{item.id}")

    assert response.status_code == 404


async def test_get_property_with_invalid_id_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/properties/not-a-uuid")

    assert response.status_code == 422


async def test_get_unknown_property_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/properties/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_sold_section_shows_no_price_and_only_authorized_photos(
    client: AsyncClient, store: Store
) -> None:
    item = await store(
        photos=2, status=PropertyStatus.SOLD, closed_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    item.photos[1].show_when_sold = True
    authorized_id = str(item.photos[1].id)

    response = await client.get(f"{BASE}/sold")

    [card] = response.json()["items"]
    assert [p["id"] for p in card["photos"]] == [authorized_id]
    assert "price" not in card
    assert "title" not in card
    assert "address" not in card
    assert card["closed_on"] == "2026-09-01"
