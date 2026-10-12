from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

BASE = "/api/v1/auth/me"

Headers = Callable[[User], dict[str, str]]


async def test_get_me_returns_profile(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    response = await client.get(BASE, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert "password_hash" not in response.json()


async def test_get_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(BASE)

    assert response.status_code == 401


async def test_get_me_with_tampered_token_returns_401(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    headers = auth_headers(user)
    headers["Authorization"] += "x"

    response = await client.get(BASE, headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_change_consent_withdraws_marketing(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    await client.post(
        f"{BASE}/consents",
        json={"purpose": "marketing", "granted": True, "policy_version": "2026-01"},
        headers=auth_headers(user),
    )

    response = await client.post(
        f"{BASE}/consents",
        json={"purpose": "marketing", "granted": False, "policy_version": "2026-01"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "purpose": "marketing",
            "granted": False,
            "policy_version": "2026-01",
            "recorded_at": response.json()[0]["recorded_at"],
        }
    ]


async def test_get_consents_returns_current_state(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    await client.post(
        f"{BASE}/consents",
        json={"purpose": "push_notifications", "granted": True, "policy_version": "2026-01"},
        headers=auth_headers(user),
    )

    response = await client.get(f"{BASE}/consents", headers=auth_headers(user))

    assert [c["purpose"] for c in response.json()] == ["push_notifications"]


async def test_change_consent_with_unknown_purpose_returns_422(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    response = await client.post(
        f"{BASE}/consents",
        json={"purpose": "telemarketing", "granted": True, "policy_version": "2026-01"},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


async def test_change_consent_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"{BASE}/consents",
        json={"purpose": "marketing", "granted": True, "policy_version": "2026-01"},
    )

    assert response.status_code == 401


async def test_export_returns_profile_and_consents(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    await client.post(
        f"{BASE}/consents",
        json={"purpose": "marketing", "granted": True, "policy_version": "2026-01"},
        headers=auth_headers(user),
    )

    response = await client.get(f"{BASE}/export", headers=auth_headers(user))

    body = response.json()
    assert response.status_code == 200
    assert body["user"]["id"] == str(user.id)
    assert body["consents"][0]["purpose"] == "marketing"


async def test_delete_me_removes_account(
    client: AsyncClient, db_session: AsyncSession, user: User, auth_headers: Headers
) -> None:
    response = await client.delete(BASE, headers=auth_headers(user))

    assert response.status_code == 204
    assert await db_session.get(User, user.id) is None


async def test_get_me_after_deletion_returns_404(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    headers = auth_headers(user)
    await client.delete(BASE, headers=headers)

    response = await client.get(BASE, headers=headers)

    assert response.status_code == 404


async def test_delete_me_as_last_admin_returns_409(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.delete(BASE, headers=auth_headers(admin))

    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"
