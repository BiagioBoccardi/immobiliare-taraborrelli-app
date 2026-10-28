import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadKind, LeadPriority
from app.models.lead import Lead
from tests.factories import make_lead

BASE = "/api/v1/lead/leads"


async def _store(db_session: AsyncSession, **overrides: object) -> Lead:
    lead = make_lead(**overrides)
    db_session.add(lead)
    await db_session.flush()
    return lead


async def test_list_leads_as_staff_returns_paginated_page(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    for _ in range(3):
        await _store(db_session)

    response = await client.get(BASE, params={"size": 2}, headers=staff_headers)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 3
    assert body["page"] == 1
    assert len(body["items"]) == 2


async def test_list_leads_filters_by_priority(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    high = await _store(db_session, priority=LeadPriority.HIGH)
    await _store(db_session, priority=LeadPriority.LOW)

    response = await client.get(BASE, params={"priority": "high"}, headers=staff_headers)

    assert [item["id"] for item in response.json()["items"]] == [str(high.id)]


async def test_list_leads_with_size_over_limit_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(BASE, params={"size": 500}, headers=staff_headers)

    assert response.status_code == 422


async def test_list_leads_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(BASE)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


async def test_list_leads_with_user_role_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.get(BASE, headers=user_headers)

    assert response.status_code == 403


async def test_list_leads_with_expired_token_returns_401(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(["staff"], exp=1)

    response = await client.get(BASE, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


async def test_get_lead_as_staff_returns_lead(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    lead = await _store(db_session, kind=LeadKind.SELL)

    response = await client.get(f"{BASE}/{lead.id}", headers=staff_headers)

    assert response.status_code == 200
    assert response.json()["kind"] == "sell"
    assert "completion_token_hash" not in response.json()


async def test_get_unknown_lead_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/{uuid.uuid4()}", headers=staff_headers)

    assert response.status_code == 404


async def test_get_lead_with_invalid_id_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/not-a-uuid", headers=staff_headers)

    assert response.status_code == 422


async def test_update_lead_sets_status_and_reminder(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    lead = await _store(db_session)

    response = await client.patch(
        f"{BASE}/{lead.id}",
        json={"status": "appointment_scheduled", "next_contact_at": "2026-10-20T10:00:00+02:00"},
        headers=staff_headers,
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "appointment_scheduled"
    assert datetime.fromisoformat(body["next_contact_at"]) == datetime(
        2026, 10, 20, 8, 0, tzinfo=UTC
    )


async def test_update_lead_with_invalid_status_returns_422(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    lead = await _store(db_session)

    response = await client.patch(
        f"{BASE}/{lead.id}", json={"status": "archived"}, headers=staff_headers
    )

    assert response.status_code == 422


async def test_update_lead_with_null_priority_returns_400(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    lead = await _store(db_session)

    response = await client.patch(
        f"{BASE}/{lead.id}", json={"priority": None}, headers=staff_headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_update"


async def test_delete_lead_as_staff_returns_204_and_removes_it(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    lead = await _store(db_session)

    response = await client.delete(f"{BASE}/{lead.id}", headers=staff_headers)

    assert response.status_code == 204
    assert await db_session.get(Lead, lead.id) is None


@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_write_endpoints_with_user_role_return_403(
    client: AsyncClient, db_session: AsyncSession, user_headers: dict[str, str], method: str
) -> None:
    lead = await _store(db_session)
    kwargs: dict[str, object] = {"headers": user_headers}
    if method == "patch":
        kwargs["json"] = {"status": "contacted"}

    response = await getattr(client, method)(f"{BASE}/{lead.id}", **kwargs)

    assert response.status_code == 403


async def test_list_leads_includes_callback_requests_without_property_fields(
    client: AsyncClient, db_session: AsyncSession, staff_headers: dict[str, str]
) -> None:
    callback = await _store(
        db_session,
        kind=LeadKind.CALLBACK,
        intention=None,
        municipality=None,
        property_type=None,
        details={"preferred_time": "evening", "source": "website"},
    )

    response = await client.get(BASE, params={"kind": "callback"}, headers=staff_headers)

    items = response.json()["items"]
    assert response.status_code == 200
    assert [item["id"] for item in items] == [str(callback.id)]
    assert items[0]["municipality"] is None
    assert items[0]["details"]["preferred_time"] == "evening"
