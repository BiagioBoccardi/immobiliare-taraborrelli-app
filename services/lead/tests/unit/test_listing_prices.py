import json

import httpx
import pytest

from app.services.listing_prices import HttpListingPrices, ListingStats

BODY = {
    "scope": "municipality",
    "listings": 7,
    "low_per_sqm": 1000,
    "median_per_sqm": 1200,
    "high_per_sqm": 1450,
}


def _client(handler: httpx.MockTransport) -> HttpListingPrices:
    return HttpListingPrices("http://property.test/", transport=handler)


async def test_stats_reads_the_property_service() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(BODY).encode())

    stats = await _client(httpx.MockTransport(handler)).stats("Chieti", "villa")

    assert stats == ListingStats("municipality", 7, 1000, 1200, 1450)
    assert seen[0].url.path == "/api/v1/property/price-stats"
    assert seen[0].url.params["municipality"] == "Chieti"
    assert seen[0].url.params["property_type"] == "villa"


async def test_stats_without_listings_returns_none() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(404, json={"code": "no_listings"}))

    assert await _client(transport).stats("Chieti", "villa") is None


@pytest.mark.parametrize(
    "response", [httpx.Response(500), httpx.Response(200, content=b"not json")]
)
async def test_stats_when_property_fails_returns_none(response: httpx.Response) -> None:
    transport = httpx.MockTransport(lambda _: response)

    assert await _client(transport).stats("Chieti", "villa") is None


async def test_stats_when_property_is_unreachable_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    assert await _client(httpx.MockTransport(handler)).stats("Chieti", "villa") is None
