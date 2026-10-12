"""Password hashing (Argon2) and access token signing."""

import uuid
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.hazmat.primitives import serialization
from py_common.security import Role


class PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2Hasher()
        # Used when the email does not exist, so login takes the same time either way.
        self._dummy_hash = self._hasher.hash("dummy-password-for-timing")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash or self._dummy_hash, password) and (
                password_hash is not None
            )
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)


def public_key_from_private(private_pem: str) -> str:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


class AccessTokenIssuer:
    def __init__(
        self,
        private_key: str,
        algorithm: str,
        audience: str,
        issuer: str,
        lifetime: timedelta,
    ) -> None:
        self._private_key = private_key
        self._algorithm = algorithm
        self._audience = audience
        self._issuer = issuer
        self.lifetime = lifetime

    def issue(self, user_id: uuid.UUID, role: Role, now: datetime) -> str:
        claims = {
            "sub": str(user_id),
            "roles": [role.value],
            "aud": self._audience,
            "iss": self._issuer,
            "iat": now,
            "exp": now + self.lifetime,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._private_key, algorithm=self._algorithm)
