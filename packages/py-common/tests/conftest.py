from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from py_common.security import TokenVerifier

AUDIENCE = "taraborrelli"
ISSUER = "taraborrelli-auth"


@pytest.fixture(scope="session")
def rsa_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def verifier(rsa_keys: tuple[str, str]) -> TokenVerifier:
    return TokenVerifier(rsa_keys[1], "RS256", AUDIENCE, ISSUER)


@pytest.fixture
def make_token(rsa_keys: tuple[str, str]) -> Callable[..., str]:
    def _make(
        roles: list[str] | None = None,
        expires_in: timedelta = timedelta(minutes=5),
        **overrides: Any,
    ) -> str:
        claims: dict[str, Any] = {
            "sub": "user-1",
            "roles": roles or [],
            "aud": AUDIENCE,
            "iss": ISSUER,
            "exp": datetime.now(UTC) + expires_in,
        }
        claims.update(overrides)
        return jwt.encode(claims, rsa_keys[0], algorithm="RS256")

    return _make
