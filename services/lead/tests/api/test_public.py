import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from tests.factories import (
    callback_request_payload,
    consent_payload,
    make_lead,
    owner_request_payload,
    valuation_payload,
)
from tests.unit.fakes import RecordingNotifier

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
