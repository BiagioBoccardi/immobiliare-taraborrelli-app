import uuid
from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from tests.factories import make_lead, owner_request_payload

BASE = "/api/v1/lead"


def _bearer(make_token: Callable[..., str], user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(['user'], sub=str(user_id))}"}


async def test_owner_request_with_token_is_linked_to_account(
    client: AsyncClient, db_session: AsyncSession, make_token: Callable[..., str]
) -> None:
    user_id = uuid.uuid4()

    response = await client.post(
        f"{BASE}/owner-requests",
        json=owner_request_payload(),
        headers=_bearer(make_token, user_id),
    )

    lead = await db_session.get(Lead, uuid.UUID(response.json()["id"]))
    assert response.status_code == 201
    assert lead is not None
    assert lead.user_id == user_id


async def test_owner_request_without_token_stays_anonymous(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(f"{BASE}/owner-requests", json=owner_request_payload())

    lead = await db_session.get(Lead, uuid.UUID(response.json()["id"]))
    assert lead is not None
    assert lead.user_id is None


async def test_owner_request_with_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"{BASE}/owner-requests",
        json=owner_request_payload(),
        headers={"Authorization": "Bearer scaduto"},
    )

    assert response.status_code == 401


async def test_my_requests_returns_only_own_requests(
    client: AsyncClient, db_session: AsyncSession, make_token: Callable[..., str]
) -> None:
    user_id = uuid.uuid4()
    own = make_lead(user_id=user_id)
    db_session.add_all([own, make_lead(user_id=uuid.uuid4()), make_lead()])
    await db_session.flush()

    response = await client.get(f"{BASE}/me/requests", headers=_bearer(make_token, user_id))

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(own.id)
    assert set(body["items"][0]) == {
        "id",
        "kind",
        "status",
        "municipality",
        "property_type",
        "created_at",
    }


async def test_my_requests_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/me/requests")

    assert response.status_code == 401


async def test_my_requests_with_page_size_over_limit_returns_422(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    response = await client.get(
        f"{BASE}/me/requests", params={"size": 500}, headers=_bearer(make_token, uuid.uuid4())
    )

    assert response.status_code == 422
