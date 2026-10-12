import uuid
from datetime import UTC, datetime, timedelta

import pytest
from py_common.errors import ConflictError, NotFoundError, UnauthorizedError
from py_common.events import InMemoryEventPublisher
from py_common.security import Role

from app.core.security import AccessTokenIssuer, PasswordHasher
from app.models.enums import ConsentPurpose
from app.schemas.auth import RegisterIn
from app.services.auth import AuthService
from app.services.tokens import hash_token
from tests.factories import (
    DEFAULT_PASSWORD,
    make_consent,
    make_refresh_token,
    make_user,
    register_payload,
)
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def publisher() -> InMemoryEventPublisher:
    return InMemoryEventPublisher()


@pytest.fixture
def service(
    uow: FakeUnitOfWork, publisher: InMemoryEventPublisher, private_key: str
) -> AuthService:
    issuer = AccessTokenIssuer(
        private_key, "RS256", "taraborrelli", "taraborrelli-auth", timedelta(minutes=15)
    )
    return AuthService(
        uow, PasswordHasher(), issuer, publisher, timedelta(days=30), clock=lambda: NOW
    )


async def test_register_creates_user_with_lowercase_email(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user, tokens = await service.register(RegisterIn.model_validate(register_payload()))

    assert uow.users.items[user.id].email == "mario.rossi@example.com"
    assert user.role is Role.USER
    assert tokens.expires_in == 900
    assert uow.commits == 1


async def test_register_records_contact_and_marketing_consents(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    payload = register_payload()
    payload["consent"]["marketing_accepted"] = True

    user, _ = await service.register(RegisterIn.model_validate(payload))

    consents = {(r.purpose, r.granted) for r in uow.consents.items if r.subject_id == user.id}
    assert consents == {(ConsentPurpose.CONTACT, True), (ConsentPurpose.MARKETING, True)}


async def test_register_stores_password_and_refresh_token_only_as_hashes(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user, tokens = await service.register(RegisterIn.model_validate(register_payload()))

    assert DEFAULT_PASSWORD not in user.password_hash
    assert uow.refresh_tokens.items[0].token_hash == hash_token(tokens.refresh_token)


async def test_register_with_existing_email_raises_email_taken(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user(email="mario.rossi@example.com"))

    with pytest.raises(ConflictError) as exc_info:
        await service.register(RegisterIn.model_validate(register_payload()))

    assert exc_info.value.code == "email_taken"


async def test_login_with_valid_credentials_returns_tokens(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user(email="a@example.com"))

    tokens = await service.login("A@example.com", DEFAULT_PASSWORD)

    assert tokens.access_token
    assert user.last_login_at == NOW


@pytest.mark.parametrize(
    ("email", "password", "active"),
    [
        ("a@example.com", "password-sbagliata", True),
        ("sconosciuto@example.com", DEFAULT_PASSWORD, True),
        ("a@example.com", DEFAULT_PASSWORD, False),
    ],
)
async def test_login_with_invalid_credentials_raises_same_error(
    service: AuthService, uow: FakeUnitOfWork, email: str, password: str, active: bool
) -> None:
    await uow.users.add(make_user(email="a@example.com", is_active=active))

    with pytest.raises(UnauthorizedError) as exc_info:
        await service.login(email, password)

    assert exc_info.value.code == "invalid_credentials"


async def test_refresh_rotates_token_within_same_family(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user())
    old = await uow.refresh_tokens.add(make_refresh_token(user, "old-token", now=NOW))

    tokens = await service.refresh("old-token")

    new = await uow.refresh_tokens.get_by_hash(hash_token(tokens.refresh_token))
    assert old.revoked_at == NOW
    assert new is not None
    assert new.family_id == old.family_id
    assert new.revoked_at is None


async def test_refresh_with_reused_token_revokes_whole_family(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user())
    family = uuid.uuid4()
    await uow.refresh_tokens.add(
        make_refresh_token(user, "used", now=NOW, family_id=family, revoked_at=NOW)
    )
    current = await uow.refresh_tokens.add(
        make_refresh_token(user, "current", now=NOW, family_id=family)
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await service.refresh("used")

    assert exc_info.value.code == "refresh_token_reused"
    assert current.revoked_at == NOW


async def test_refresh_with_expired_token_raises_invalid(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user())
    await uow.refresh_tokens.add(
        make_refresh_token(user, "expired", now=NOW, expires_at=NOW - timedelta(seconds=1))
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await service.refresh("expired")

    assert exc_info.value.code == "invalid_refresh_token"


async def test_refresh_with_unknown_token_raises_invalid(service: AuthService) -> None:
    with pytest.raises(UnauthorizedError) as exc_info:
        await service.refresh("never-issued")

    assert exc_info.value.code == "invalid_refresh_token"


async def test_refresh_for_disabled_user_revokes_session(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user(is_active=False))
    token = await uow.refresh_tokens.add(make_refresh_token(user, "t", now=NOW))

    with pytest.raises(UnauthorizedError):
        await service.refresh("t")

    assert token.revoked_at == NOW


async def test_logout_revokes_family(service: AuthService, uow: FakeUnitOfWork) -> None:
    user = await uow.users.add(make_user())
    token = await uow.refresh_tokens.add(make_refresh_token(user, "t", now=NOW))

    await service.logout("t")

    assert token.revoked_at == NOW


async def test_logout_with_unknown_token_does_nothing(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    await service.logout("never-issued")

    assert uow.commits == 0


async def test_delete_user_removes_data_and_emits_event(
    service: AuthService, uow: FakeUnitOfWork, publisher: InMemoryEventPublisher
) -> None:
    user = await uow.users.add(make_user())
    await uow.consents.add(make_consent(user.id))

    await service.delete_user(user.id)

    assert user.id not in uow.users.items
    assert uow.consents.items == []
    [event] = publisher.events
    assert event.event_type == "auth.user_deleted"
    assert event.payload.user_id == user.id


async def test_delete_last_admin_raises_conflict(service: AuthService, uow: FakeUnitOfWork) -> None:
    admin = await uow.users.add(make_user(role=Role.ADMIN))

    with pytest.raises(ConflictError) as exc_info:
        await service.delete_user(admin.id)

    assert exc_info.value.code == "last_admin"


async def test_delete_unknown_user_raises_not_found(service: AuthService) -> None:
    with pytest.raises(NotFoundError):
        await service.delete_user(uuid.uuid4())


async def test_export_user_contains_profile_and_consents(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user())
    await uow.consents.add(make_consent(user.id, purpose=ConsentPurpose.MARKETING))

    export = await service.export_user(user.id)

    assert export.user.id == user.id
    assert [c.purpose for c in export.consents] == [ConsentPurpose.MARKETING]
    assert export.exported_at == NOW
