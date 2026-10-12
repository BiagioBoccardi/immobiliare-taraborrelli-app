import uuid
from datetime import UTC, datetime, timedelta

from py_common.security import Role, TokenVerifier

from app.core.security import AccessTokenIssuer, PasswordHasher, public_key_from_private

NOW = datetime.now(UTC)


def test_verify_with_correct_password_returns_true() -> None:
    hasher = PasswordHasher()
    password_hash = hasher.hash("una-password-lunga")

    assert hasher.verify(password_hash, "una-password-lunga")


def test_verify_with_wrong_password_returns_false() -> None:
    hasher = PasswordHasher()
    password_hash = hasher.hash("una-password-lunga")

    assert not hasher.verify(password_hash, "sbagliata")


def test_verify_without_hash_returns_false() -> None:
    result = PasswordHasher().verify(None, "dummy-password-for-timing")

    assert result is False


def test_verify_with_malformed_hash_returns_false() -> None:
    result = PasswordHasher().verify("not-an-argon2-hash", "qualsiasi")

    assert result is False


def test_hash_uses_argon2id() -> None:
    password_hash = PasswordHasher().hash("una-password-lunga")

    assert password_hash.startswith("$argon2id$")


def test_issued_token_is_verified_with_derived_public_key(private_key: str) -> None:
    issuer = AccessTokenIssuer(
        private_key, "RS256", "taraborrelli", "taraborrelli-auth", timedelta(minutes=15)
    )
    verifier = TokenVerifier(
        public_key_from_private(private_key), "RS256", "taraborrelli", "taraborrelli-auth"
    )
    user_id = uuid.uuid4()

    principal = verifier.verify(issuer.issue(user_id, Role.STAFF, NOW))

    assert principal.subject == str(user_id)
    assert principal.roles == frozenset({Role.STAFF})
