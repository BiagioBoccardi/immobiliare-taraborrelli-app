"""Address search for the valuation: OpenStreetMap Nominatim, called from the server.

Nominatim's usage policy: at most one request per second, an identifying User-Agent, no
search-as-you-type and the "© OpenStreetMap" attribution (shown by the app). Results are
cached, so the same address is asked only once.
"""

import asyncio
import logging
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from py_common.errors import AppError

logger = logging.getLogger(__name__)
# httpx logs every URL at INFO level, and the URL contains the searched address (personal data).
logging.getLogger("httpx").setLevel(logging.WARNING)


class GeocodingUnavailableError(AppError):
    status_code = 503
    code = "geocoding_unavailable"
    message = "The address search is not available at the moment"


@dataclass(frozen=True)
class Place:
    label: str
    latitude: float
    longitude: float
    municipality: str | None
    road: str | None
    house_number: str | None
    postcode: str | None


class Geocoder(Protocol):
    async def search(self, query: str) -> list[Place]: ...


def _municipality(address: dict[str, str]) -> str | None:
    for key in ("city", "town", "village", "municipality", "hamlet", "suburb"):
        if address.get(key):
            return address[key]
    return None


def _place(item: dict[str, Any]) -> Place:
    address: dict[str, str] = item.get("address") or {}
    road, number = address.get("road"), address.get("house_number")
    municipality = _municipality(address)
    if road:
        label = ", ".join(p for p in (f"{road} {number}" if number else road, municipality) if p)
    else:
        label = str(item.get("display_name", ""))
    return Place(
        label=label,
        latitude=float(item["lat"]),
        longitude=float(item["lon"]),
        municipality=municipality,
        road=road,
        house_number=number,
        postcode=address.get("postcode"),
    )


class NominatimGeocoder:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        email: str | None = None,
        viewbox: str | None = None,
        timeout: float = 5.0,
        min_interval: float = 1.0,
        cache_size: int = 500,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._url = base_url.rstrip("/") + "/search"
        self._headers = {"User-Agent": user_agent, "Accept-Language": "it"}
        self._email = email
        self._viewbox = viewbox
        self._timeout = timeout
        self._min_interval = min_interval
        self._cache: OrderedDict[str, list[Place]] = OrderedDict()
        self._cache_size = cache_size
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last_request: float | None = None

    async def search(self, query: str) -> list[Place]:
        key = re.sub(r"\s+", " ", query).strip().lower()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        async with self._lock:
            if key in self._cache:  # found by a request that was waiting before this one
                return self._cache[key]
            if self._last_request is not None:
                wait = self._last_request + self._min_interval - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            self._last_request = self._clock()
            places = await self._request(query)
        self._cache[key] = places
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return places

    async def _request(self, query: str) -> list[Place]:
        params: dict[str, str | int] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 5,
            "countrycodes": "it",
        }
        if self._viewbox:
            params["viewbox"] = self._viewbox  # preference for the agency's area, not a limit
        if self._email:
            params["email"] = self._email
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(self._url, params=params)
                response.raise_for_status()
                items = response.json()
            if not isinstance(items, list):
                raise TypeError("unexpected response")
            return [_place(item) for item in items]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            # The address is personal data: it is never logged.
            logger.warning("geocoding failed: %s", type(exc).__name__)
            raise GeocodingUnavailableError() from exc
