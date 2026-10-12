import uuid

from httpx import AsyncClient
from py_common.security import Role, TokenVerifier
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import public_key_from_private
from app.models.consent import ConsentRecord
from app.models.user import User
from tests.factories import DEFAULT_PASSWORD, register_payload

BASE = "/api/v1/auth"


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.json() == {"status": "ok"}


async def test_register_returns_201_with_verifiable_access_token(
    client: AsyncClient, private_key: str
) -> None:
    response = await client.post(f"{BASE}/register", json=register_payload())

    body = response.json()
    verifier = TokenVerifier(
        public_key_from_private(private_key), "RS256", "taraborrelli", "taraborrelli-auth"
    )
    assert response.status_code == 201
    assert body["token_type"] == "bearer"
    assert verifier.verify(body["access_token"]).roles == frozenset({Role.USER})


async def test_register_records_consents_in_registry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(f"{BASE}/register", json=register_payload())

    records = (await db_session.scalars(select(ConsentRecord))).all()

    assert {(r.purpose.value, r.granted) for r in records} == {
        ("contact", True),
        ("marketing", False),
    }
    assert {r.policy_version for r in records} == {"2026-01"}


async def test_register_with_existing_email_returns_409(client: AsyncClient, user: User) -> None:
    response = await client.post(f"{BASE}/register", json=register_payload(email=user.email))

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


async def test_register_with_short_password_returns_422(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/register", json=register_payload(password="corta"))

    assert response.status_code == 422
    assert "corta" not in response.text


async def test_register_cannot_choose_role(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/register", json=register_payload(role="admin"))

    assert response.status_code == 422


async def test_login_with_valid_credentials_returns_200(client: AsyncClient, user: User) -> None:
    response = await client.post(
        f"{BASE}/login", json={"email": user.email.upper(), "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["refresh_token"]


async def test_login_with_wrong_password_returns_401(client: AsyncClient, user: User) -> None:
    response = await client.post(
        f"{BASE}/login", json={"email": user.email, "password": "password-sbagliata"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_login_without_password_returns_422(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/login", json={"email": "a@example.com"})

    assert response.status_code == 422


async def test_refresh_rotates_and_old_token_is_rejected(client: AsyncClient, user: User) -> None:
    login = (
        await client.post(f"{BASE}/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    ).json()
    refreshed = await client.post(f"{BASE}/refresh", json={"refresh_token": login["refresh_token"]})

    reused = await client.post(f"{BASE}/refresh", json={"refresh_token": login["refresh_token"]})

    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != login["refresh_token"]
    assert reused.status_code == 401
    assert reused.json()["code"] == "refresh_token_reused"


async def test_refresh_after_reuse_revokes_new_token_too(client: AsyncClient, user: User) -> None:
    login = (
        await client.post(f"{BASE}/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    ).json()
    new = (
        await client.post(f"{BASE}/refresh", json={"refresh_token": login["refresh_token"]})
    ).json()
    await client.post(f"{BASE}/refresh", json={"refresh_token": login["refresh_token"]})

    response = await client.post(f"{BASE}/refresh", json={"refresh_token": new["refresh_token"]})

    assert response.status_code == 401


async def test_refresh_without_body_returns_422(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/refresh", json={})

    assert response.status_code == 422


async def test_logout_returns_204_and_revokes_refresh(client: AsyncClient, user: User) -> None:
    login = (
        await client.post(f"{BASE}/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    ).json()

    response = await client.post(f"{BASE}/logout", json={"refresh_token": login["refresh_token"]})

    after = await client.post(f"{BASE}/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 204
    assert after.status_code == 401


async def test_logout_with_unknown_token_returns_204(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/logout", json={"refresh_token": uuid.uuid4().hex})

    assert response.status_code == 204


async def test_public_key_returns_pem_matching_private_key(
    client: AsyncClient, private_key: str
) -> None:
    response = await client.get(f"{BASE}/public-key")

    assert response.status_code == 200
    assert response.text == public_key_from_private(private_key)


async def test_registered_user_password_is_hashed_with_argon2(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(f"{BASE}/register", json=register_payload())

    user = (await db_session.scalars(select(User))).one()

    assert user.password_hash.startswith("$argon2id$")
