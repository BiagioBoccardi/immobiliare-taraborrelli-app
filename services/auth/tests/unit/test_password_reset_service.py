from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from py_common.errors import AppError

from app.core.security import PasswordHasher
from app.models.user import User
from app.services.password_reset import PasswordResetService, hash_code, new_code
from tests.factories import DEFAULT_PASSWORD, make_refresh_token, make_user
from tests.unit.fakes import FakeEmailSender, FakeUnitOfWork

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
NEW_PASSWORD = "Nuova-password-123"


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def build(
    sender: FakeEmailSender | None = None,
) -> tuple[PasswordResetService, FakeUnitOfWork, FakeEmailSender, Clock]:
    uow = FakeUnitOfWork()
    sender = sender or FakeEmailSender()
    clock = Clock()
    service = PasswordResetService(
        uow, PasswordHasher(), sender, clock=clock, make_code=lambda: "123456"
    )
    return service, uow, sender, clock


async def _with_user(uow: FakeUnitOfWork, **overrides: Any) -> User:
    user = make_user(**overrides)
    await uow.users.add(user)
    return user


def test_new_code_has_six_digits() -> None:
    codes = {new_code() for _ in range(50)}

    assert all(len(code) == 6 and code.isdigit() for code in codes)


async def test_request_sends_code_by_email_and_stores_only_its_hash() -> None:
    service, uow, sender, _ = build()
    user = await _with_user(uow, email="anna@example.test", full_name="Anna Bianchi")

    await service.request("anna@example.test")

    (email,) = sender.sent
    assert email.to == "anna@example.test"
    assert "123456" in email.text
    assert email.text.startswith("Ciao Anna,")
    (reset,) = uow.password_resets.items
    assert reset.code_hash == hash_code(user.id, "123456")
    assert "123456" not in reset.code_hash
    assert reset.expires_at == NOW + timedelta(minutes=15)


async def test_request_for_unknown_email_sends_nothing_and_does_not_fail() -> None:
    service, uow, sender, _ = build()

    await service.request("nessuno@example.test")

    assert sender.sent == []
    assert uow.password_resets.items == []


async def test_request_for_disabled_account_sends_nothing() -> None:
    service, uow, sender, _ = build()
    await _with_user(uow, email="off@example.test", is_active=False)

    await service.request("off@example.test")

    assert sender.sent == []


async def test_request_twice_within_a_minute_sends_one_email() -> None:
    service, uow, sender, clock = build()
    await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")
    clock.now = NOW + timedelta(seconds=30)

    await service.request("anna@example.test")

    assert len(sender.sent) == 1


async def test_new_request_replaces_the_previous_code() -> None:
    service, uow, _, clock = build()
    await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")
    clock.now = NOW + timedelta(minutes=2)

    await service.request("anna@example.test")

    first, second = uow.password_resets.items
    assert first.used_at == clock.now
    assert second.used_at is None


async def test_request_when_email_fails_does_not_raise() -> None:
    service, uow, _, _ = build(FakeEmailSender(fail=True))
    await _with_user(uow, email="anna@example.test")

    await service.request("anna@example.test")

    assert len(uow.password_resets.items) == 1


async def test_reset_with_right_code_changes_password_and_closes_sessions() -> None:
    service, uow, _, _ = build()
    user = await _with_user(uow, email="anna@example.test")
    token = make_refresh_token(user, "refresh-token", now=NOW)
    await uow.refresh_tokens.add(token)
    await service.request("anna@example.test")

    await service.reset("anna@example.test", "123456", NEW_PASSWORD)

    hasher = PasswordHasher()
    assert hasher.verify(user.password_hash, NEW_PASSWORD)
    assert not hasher.verify(user.password_hash, DEFAULT_PASSWORD)
    assert token.revoked_at == NOW
    assert uow.password_resets.items[0].used_at == NOW


async def test_reset_code_cannot_be_used_twice() -> None:
    service, uow, _, _ = build()
    await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")
    await service.reset("anna@example.test", "123456", NEW_PASSWORD)

    with pytest.raises(AppError) as exc_info:
        await service.reset("anna@example.test", "123456", "Altra-password-456")

    assert exc_info.value.code == "invalid_reset_code"


async def test_reset_with_expired_code_raises_invalid_reset_code() -> None:
    service, uow, _, clock = build()
    await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")
    clock.now = NOW + timedelta(minutes=16)

    with pytest.raises(AppError) as exc_info:
        await service.reset("anna@example.test", "123456", NEW_PASSWORD)

    assert exc_info.value.code == "invalid_reset_code"


async def test_reset_with_wrong_code_counts_the_attempt() -> None:
    service, uow, _, _ = build()
    user = await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")

    with pytest.raises(AppError):
        await service.reset("anna@example.test", "000000", NEW_PASSWORD)

    assert uow.password_resets.items[0].attempts == 1
    assert PasswordHasher().verify(user.password_hash, DEFAULT_PASSWORD)


async def test_reset_after_five_wrong_codes_blocks_even_the_right_one() -> None:
    service, uow, _, _ = build()
    await _with_user(uow, email="anna@example.test")
    await service.request("anna@example.test")
    for _ in range(5):
        with pytest.raises(AppError):
            await service.reset("anna@example.test", "000000", NEW_PASSWORD)

    with pytest.raises(AppError) as exc_info:
        await service.reset("anna@example.test", "123456", NEW_PASSWORD)

    assert exc_info.value.code == "invalid_reset_code"


async def test_reset_for_unknown_email_raises_the_same_error() -> None:
    service, _, _, _ = build()

    with pytest.raises(AppError) as exc_info:
        await service.reset("nessuno@example.test", "123456", NEW_PASSWORD)

    assert exc_info.value.code == "invalid_reset_code"
