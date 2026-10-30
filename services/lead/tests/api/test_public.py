import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from py_common.ratelimit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_geocoder, get_listing_prices
from app.main import create_app
from app.models.lead import Lead
from app.services.geocoding import GeocodingUnavailableError, Place
from app.services.listing_prices import ListingStats
from tests.factories import (
    callback_request_payload,
    consent_payload,
    make_lead,
    omi_kmz,
    omi_values_csv,
    omi_zones_csv,
    owner_request_payload,
    valuation_payload,
)
from tests.unit.fakes import FakeListingPrices, RecordingNotifier

BASE = "/api/v1/lead"


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_valuation_returns_201_with_completion_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(f"{BASE}/valuations", json=valuation_payload())

    body = response.json()
    assert response.status_code == 201
    assert body["kind"] == "valuation"
    assert body["completion_token"]
    lead = await db_session.get(Lead, uuid.UUID(body["id"]))
    assert lead is not None
    assert lead.phone == "+393330000000"


async def test_create_valuation_without_phone_returns_422(client: AsyncClient) -> None:
    payload = valuation_payload()
    del payload["phone"]

    response = await client.post(f"{BASE}/valuations", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_create_valuation_without_privacy_consent_returns_422(client: AsyncClient) -> None:
    payload = valuation_payload(consent=consent_payload(privacy_accepted=False))

    response = await client.post(f"{BASE}/valuations", json=payload)

    assert response.status_code == 422


async def test_create_valuation_validation_error_does_not_echo_name(client: AsyncClient) -> None:
    payload = valuation_payload(full_name="Giulia Verdi", phone="not-a-phone")

    response = await client.post(f"{BASE}/valuations", json=payload)

    assert response.status_code == 422
    assert "Giulia" not in response.text
    assert "not-a-phone" not in response.text


async def test_complete_valuation_with_token_returns_204(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post(f"{BASE}/valuations", json=valuation_payload())).json()

    response = await client.put(
        f"{BASE}/valuations/{created['id']}/details",
        json={"bathrooms": 2, "sell_timeline": "within_6_months", "expected_price_unknown": True},
        headers={"X-Completion-Token": created["completion_token"]},
    )

    assert response.status_code == 204
    lead = await db_session.get(Lead, uuid.UUID(created["id"]))
    assert lead is not None
    assert lead.details["sell_timeline"] == "within_6_months"


async def test_complete_valuation_with_wrong_token_returns_404(client: AsyncClient) -> None:
    created = (await client.post(f"{BASE}/valuations", json=valuation_payload())).json()

    response = await client.put(
        f"{BASE}/valuations/{created['id']}/details",
        json={"bathrooms": 2},
        headers={"X-Completion-Token": "wrong"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_complete_valuation_without_token_returns_422(client: AsyncClient) -> None:
    response = await client.put(f"{BASE}/valuations/{uuid.uuid4()}/details", json={})

    assert response.status_code == 422


async def test_complete_valuation_with_invalid_details_returns_422(client: AsyncClient) -> None:
    created = (await client.post(f"{BASE}/valuations", json=valuation_payload())).json()

    response = await client.put(
        f"{BASE}/valuations/{created['id']}/details",
        json={"year_built": 1500},
        headers={"X-Completion-Token": created["completion_token"]},
    )

    assert response.status_code == 422


async def test_complete_valuation_after_window_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lead = make_lead(token="secret", created_at=datetime.now(UTC) - timedelta(days=8))
    db_session.add(lead)
    await db_session.flush()

    response = await client.put(
        f"{BASE}/valuations/{lead.id}/details",
        json={"bathrooms": 1},
        headers={"X-Completion-Token": "secret"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "completion_window_expired"


async def test_create_owner_request_returns_201(client: AsyncClient) -> None:
    response = await client.post(
        f"{BASE}/owner-requests", json=owner_request_payload(kind="rent", message="Bilocale")
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "rent"
    assert "completion_token" not in response.json()


async def test_create_owner_request_with_missing_intention_returns_422(
    client: AsyncClient,
) -> None:
    payload = owner_request_payload()
    del payload["intention"]

    response = await client.post(f"{BASE}/owner-requests", json=payload)

    assert response.status_code == 422


async def _load_omi(client: AsyncClient, headers: dict[str, str]) -> None:
    files = [
        ("quotes", ("valori.csv", omi_values_csv(), "text/csv")),
        ("zones", ("zone.csv", omi_zones_csv(), "text/csv")),
        ("perimeters", ("chieti.kmz", omi_kmz(), "application/zip")),
    ]
    response = await client.post("/api/v1/lead/omi", files=files, headers=headers)
    assert response.status_code == 201


async def test_create_valuation_with_position_returns_indicative_estimate(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    await _load_omi(client, staff_headers)
    payload = valuation_payload(latitude=42.35, longitude=14.16, cadastral_category="A2")

    response = await client.post(f"{BASE}/valuations", json=payload)

    body = response.json()
    assert response.status_code == 201
    assert body["estimate"]["zone_code"] == "B1"
    assert body["estimate"]["min_value"] < body["estimate"]["max_value"]
    assert body["estimate_unavailable"] is None


async def test_create_valuation_with_latitude_only_returns_422(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/valuations", json=valuation_payload(latitude=42.35))

    assert response.status_code == 422


async def test_create_valuation_with_unknown_cadastral_category_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"{BASE}/valuations", json=valuation_payload(cadastral_category="C1")
    )

    assert response.status_code == 422


class FakeGeocoder:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> list[Place]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return [
            Place("Via di Prova 1, Chieti", 42.35, 14.16, "Chieti", "Via di Prova", "1", "66100")
        ]


async def test_geocode_returns_matching_places(app: FastAPI, client: AsyncClient) -> None:
    geocoder = FakeGeocoder()
    app.dependency_overrides[get_geocoder] = lambda: geocoder

    response = await client.get("/api/v1/lead/geocode", params={"q": "via di prova 1 chieti"})

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["label"] == "Via di Prova 1, Chieti"
    assert body["items"][0]["municipality"] == "Chieti"


async def test_geocode_with_too_short_text_returns_422(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder()

    response = await client.get("/api/v1/lead/geocode", params={"q": "vi"})

    assert response.status_code == 422


async def test_geocode_when_service_is_down_returns_503(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder(GeocodingUnavailableError())

    response = await client.get("/api/v1/lead/geocode", params={"q": "via di prova chieti"})

    assert response.status_code == 503
    assert response.json()["code"] == "geocoding_unavailable"


async def test_create_callback_request_returns_201_and_stores_lead(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(f"{BASE}/callback-requests", json=callback_request_payload())

    body = response.json()
    assert response.status_code == 201
    assert body["kind"] == "callback"
    lead = await db_session.get(Lead, uuid.UUID(body["id"]))
    assert lead is not None
    assert lead.details["preferred_time"] == "morning"


async def test_create_callback_request_without_privacy_consent_returns_422(
    client: AsyncClient,
) -> None:
    payload = callback_request_payload(consent=consent_payload(privacy_accepted=False))

    response = await client.post(f"{BASE}/callback-requests", json=payload)

    assert response.status_code == 422


async def test_create_callback_request_without_consent_field_returns_422(
    client: AsyncClient,
) -> None:
    payload = callback_request_payload()
    del payload["consent"]

    response = await client.post(f"{BASE}/callback-requests", json=payload)

    assert response.status_code == 422


async def test_create_callback_request_with_unknown_time_slot_returns_422(
    client: AsyncClient,
) -> None:
    payload = callback_request_payload(preferred_time="notte")

    response = await client.post(f"{BASE}/callback-requests", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_create_callback_request_with_long_message_returns_422(
    client: AsyncClient,
) -> None:
    payload = callback_request_payload(message="a" * 501)

    response = await client.post(f"{BASE}/callback-requests", json=payload)

    assert response.status_code == 422


async def test_create_callback_request_validation_error_does_not_echo_contacts(
    client: AsyncClient,
) -> None:
    payload = callback_request_payload(email="luca.neri-at-example", phone="not-a-phone")

    response = await client.post(f"{BASE}/callback-requests", json=payload)

    assert response.status_code == 422
    assert "luca.neri" not in response.text
    assert "not-a-phone" not in response.text


async def test_create_callback_request_notifies_the_agency(
    app: FastAPI, client: AsyncClient
) -> None:
    notifier = RecordingNotifier()
    app.state.staff_notifier = notifier

    response = await client.post(f"{BASE}/callback-requests", json=callback_request_payload())

    assert response.status_code == 201
    assert [str(lead.id) for lead in notifier.notified] == [response.json()["id"]]


async def test_create_callback_request_over_the_rate_limit_returns_429(
    app: FastAPI, client: AsyncClient
) -> None:
    app.state.forms_limiter = RateLimiter(limit=2, window_seconds=60)
    visitor = {"x-nf-client-connection-ip": "203.0.113.7"}
    for _ in range(2):
        await client.post(
            f"{BASE}/callback-requests", json=callback_request_payload(), headers=visitor
        )

    response = await client.post(
        f"{BASE}/callback-requests", json=callback_request_payload(), headers=visitor
    )

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"


async def test_rate_limit_does_not_block_other_visitors(app: FastAPI, client: AsyncClient) -> None:
    app.state.forms_limiter = RateLimiter(limit=1, window_seconds=60)
    await client.post(
        f"{BASE}/owner-requests",
        json=owner_request_payload(),
        headers={"x-nf-client-connection-ip": "203.0.113.7"},
    )

    response = await client.post(
        f"{BASE}/owner-requests",
        json=owner_request_payload(),
        headers={"x-nf-client-connection-ip": "198.51.100.9"},
    )

    assert response.status_code == 201


def test_create_app_enables_the_forms_limit_only_when_configured(settings: Settings) -> None:
    off = create_app(settings)
    on = create_app(settings.model_copy(update={"rate_limit_enabled": True}))

    assert off.state.forms_limiter is None
    assert isinstance(on.state.forms_limiter, RateLimiter)


async def test_create_valuation_without_omi_returns_estimate_from_agency_listings(
    app: FastAPI, client: AsyncClient
) -> None:
    stats = ListingStats("municipality", 6, 1000, 1150, 1300)
    app.dependency_overrides[get_listing_prices] = lambda: FakeListingPrices(stats)

    response = await client.post(f"{BASE}/valuations", json=valuation_payload(surface_sqm=100))

    body = response.json()
    assert response.status_code == 201
    assert body["estimate"]["basis"] == "agency_listings"
    assert body["estimate"]["listings"] == 6
    assert body["estimate"]["min_value"] == 92_000
