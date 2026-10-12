import uuid
from collections.abc import Callable

from httpx import AsyncClient

from app.models.user import User
from tests.factories import DEFAULT_PASSWORD, staff_payload

BASE = "/api/v1/auth/users"

Headers = Callable[[User], dict[str, str]]


async def test_create_staff_as_admin_returns_201(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.post(f"{BASE}/staff", json=staff_payload(), headers=auth_headers(admin))

    assert response.status_code == 201
    assert response.json()["role"] == "staff"


async def test_created_staff_can_log_in(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    await client.post(f"{BASE}/staff", json=staff_payload(), headers=auth_headers(admin))

    response = await client.post(
        "/api/v1/auth/login", json={"email": "agente@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200


async def test_create_staff_with_user_role_returns_422(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.post(
        f"{BASE}/staff", json=staff_payload(role="user"), headers=auth_headers(admin)
    )

    assert response.status_code == 422


async def test_create_staff_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/staff", json=staff_payload())

    assert response.status_code == 401


async def test_create_staff_with_user_role_returns_403(
    client: AsyncClient, user: User, auth_headers: Headers
) -> None:
    response = await client.post(f"{BASE}/staff", json=staff_payload(), headers=auth_headers(user))

    assert response.status_code == 403


async def test_create_staff_with_staff_role_returns_403(
    client: AsyncClient, staff: User, auth_headers: Headers
) -> None:
    response = await client.post(f"{BASE}/staff", json=staff_payload(), headers=auth_headers(staff))

    assert response.status_code == 403


async def test_list_users_as_admin_returns_page(
    client: AsyncClient, admin: User, staff: User, auth_headers: Headers
) -> None:
    response = await client.get(BASE, params={"role": "staff"}, headers=auth_headers(admin))

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(staff.id)


async def test_list_users_with_invalid_role_returns_422(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.get(BASE, params={"role": "owner"}, headers=auth_headers(admin))

    assert response.status_code == 422


async def test_deactivate_user_blocks_login(
    client: AsyncClient, admin: User, user: User, auth_headers: Headers
) -> None:
    await client.patch(f"{BASE}/{user.id}", json={"is_active": False}, headers=auth_headers(admin))

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 401


async def test_demote_last_admin_returns_409(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.patch(
        f"{BASE}/{admin.id}", json={"role": "staff"}, headers=auth_headers(admin)
    )

    assert response.status_code == 409


async def test_update_unknown_user_returns_404(
    client: AsyncClient, admin: User, auth_headers: Headers
) -> None:
    response = await client.patch(
        f"{BASE}/{uuid.uuid4()}", json={"is_active": False}, headers=auth_headers(admin)
    )

    assert response.status_code == 404


async def test_update_user_as_staff_returns_403(
    client: AsyncClient, staff: User, user: User, auth_headers: Headers
) -> None:
    response = await client.patch(
        f"{BASE}/{user.id}", json={"role": "admin"}, headers=auth_headers(staff)
    )

    assert response.status_code == 403
