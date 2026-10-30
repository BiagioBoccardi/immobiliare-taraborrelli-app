"""€/m² of the agency's own listings, read from the property service.

Used for the indicative estimate when no OMI quotation covers the address. A direct HTTP
read (section 3: only for indispensable reads, with timeout and error handling): if the
property service does not answer, the valuation request is stored anyway, without estimate.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

logger = logging.getLogger(__name__)

ListingScope = Literal["municipality_type", "municipality", "agency_type", "agency"]


@dataclass(frozen=True)
class ListingStats:
    scope: ListingScope
    listings: int
    low_per_sqm: int
    median_per_sqm: int
    high_per_sqm: int


class ListingPrices(Protocol):
    async def stats(self, municipality: str, property_type: str) -> ListingStats | None: ...


class HttpListingPrices:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/v1/property/price-stats"
        self._timeout = timeout
        self._transport = transport

    async def stats(self, municipality: str, property_type: str) -> ListingStats | None:
        params = {"municipality": municipality, "property_type": property_type}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as c:
                response = await c.get(self._url, params=params)
            if response.status_code == 404:
                return None  # the agency has no sale listing with price and surface yet
            response.raise_for_status()
            body = response.json()
            return ListingStats(
                scope=body["scope"],
                listings=int(body["listings"]),
                low_per_sqm=int(body["low_per_sqm"]),
                median_per_sqm=int(body["median_per_sqm"]),
                high_per_sqm=int(body["high_per_sqm"]),
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("listing prices unavailable: %s", type(exc).__name__)
            return None
