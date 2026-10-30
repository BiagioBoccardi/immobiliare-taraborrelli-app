from typing import Any

from httpx import AsyncClient

from app.models.enums import Contract, PropertyStatus, PropertyType

URL = "/api/v1/property/price-stats"


async def test_price_stats_returns_range_of_sale_listings(client: AsyncClient, store: Any) -> None:
    for price in (100_000, 120_000, 140_000):
        await store(price=price, surface_sqm=100)
    await store(price=900, contract=Contract.RENT)
    await store(price=1_000_000, status=PropertyStatus.DRAFT)

    response = await client.get(
        URL, params={"municipality": "Chieti", "property_type": "apartment"}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["scope"] == "municipality_type"
    assert body["listings"] == 3
    assert body["median_per_sqm"] == 1200


async def test_price_stats_counts_sold_listings(client: AsyncClient, store: Any) -> None:
    await store(
        price=150_000, surface_sqm=100, status=PropertyStatus.SOLD, property_type=PropertyType.HOUSE
    )

    response = await client.get(URL, params={"property_type": "house"})

    assert response.json()["listings"] == 1


async def test_price_stats_without_listings_returns_404(client: AsyncClient) -> None:
    response = await client.get(URL, params={"municipality": "Chieti"})

    assert response.status_code == 404
    assert response.json()["code"] == "no_listings"


async def test_price_stats_with_unknown_type_returns_422(client: AsyncClient) -> None:
    response = await client.get(URL, params={"property_type": "castello"})

    assert response.status_code == 422
