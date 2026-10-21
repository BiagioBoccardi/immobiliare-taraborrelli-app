from httpx import AsyncClient

from app.models.user import User
from tests.factories import DEFAULT_PASSWORD
from tests.unit.fakes import FakeEmailSender

BASE = "/api/v1/auth"
NEW_PASSWORD = "Nuova-password-123"


def code_from(sender: FakeEmailSender) -> str:
    return next(word for word in sender.sent[-1].text.split() if word.isdigit() and len(word) == 6)


async def test_forgot_password_for_existing_email_returns_202_and_sends_code(
    client: AsyncClient, user: User, email_sender: FakeEmailSender
) -> None:
    response = await client.post(f"{BASE}/password/forgot", json={"email": user.email})

    assert response.status_code == 202
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0].to == user.email


async def test_forgot_password_for_unknown_email_returns_the_same_202(
    client: AsyncClient, email_sender: FakeEmailSender
) -> None:
    response = await client.post(f"{BASE}/password/forgot", json={"email": "no@example.test"})

    assert response.status_code == 202
    assert email_sender.sent == []


async def test_forgot_password_with_invalid_email_returns_422(client: AsyncClient) -> None:
    response = await client.post(f"{BASE}/password/forgot", json={"email": "non-email"})

    assert response.status_code == 422


async def test_reset_password_with_code_lets_login_with_new_password(
    client: AsyncClient, user: User, email_sender: FakeEmailSender
) -> None:
    await client.post(f"{BASE}/password/forgot", json={"email": user.email})
    code = code_from(email_sender)

    response = await client.post(
        f"{BASE}/password/reset",
        json={"email": user.email, "code": code, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    login = await client.post(f"{BASE}/login", json={"email": user.email, "password": NEW_PASSWORD})
    assert login.status_code == 200
    old = await client.post(
        f"{BASE}/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert old.status_code == 401


async def test_reset_password_closes_existing_sessions(
    client: AsyncClient, user: User, email_sender: FakeEmailSender
) -> None:
    tokens = (
        await client.post(f"{BASE}/login", json={"email": user.email, "password": DEFAULT_PASSWORD})
    ).json()
    await client.post(f"{BASE}/password/forgot", json={"email": user.email})
    await client.post(
        f"{BASE}/password/reset",
        json={"email": user.email, "code": code_from(email_sender), "new_password": NEW_PASSWORD},
    )

    response = await client.post(f"{BASE}/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 401


async def test_reset_password_with_wrong_code_returns_400(
    client: AsyncClient, user: User, email_sender: FakeEmailSender
) -> None:
    await client.post(f"{BASE}/password/forgot", json={"email": user.email})
    wrong = "000000" if code_from(email_sender) != "000000" else "111111"

    response = await client.post(
        f"{BASE}/password/reset",
        json={"email": user.email, "code": wrong, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_reset_code"


async def test_reset_password_with_short_password_returns_422(
    client: AsyncClient, user: User
) -> None:
    response = await client.post(
        f"{BASE}/password/reset",
        json={"email": user.email, "code": "123456", "new_password": "corta"},
    )

    assert response.status_code == 422


async def test_reset_password_with_malformed_code_returns_422(
    client: AsyncClient, user: User
) -> None:
    response = await client.post(
        f"{BASE}/password/reset",
        json={"email": user.email, "code": "12ab", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 422
