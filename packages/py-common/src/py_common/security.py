"""Verification of access tokens issued by the auth service, using its public key."""

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from py_common.errors import ForbiddenError, UnauthorizedError


class Role(StrEnum):
    USER = "user"
    STAFF = "staff"
    ADMIN = "admin"


STAFF_ROLES = frozenset({Role.STAFF, Role.ADMIN})


class Principal(BaseModel):
    subject: str
    roles: frozenset[Role]

    @property
    def is_staff(self) -> bool:
        return bool(self.roles & STAFF_ROLES)


class TokenVerifier:
    def __init__(self, public_key: str, algorithm: str, audience: str, issuer: str) -> None:
        self._public_key = public_key
        self._algorithm = algorithm
        self._audience = audience
        self._issuer = issuer

    @property
    def public_key(self) -> str:
        return self._public_key

    def verify(self, token: str) -> Principal:
        if not self._public_key:
            raise UnauthorizedError("Token verification is not configured")
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Token expired", code="token_expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid token", code="invalid_token") from exc
        roles = frozenset(Role(r) for r in claims.get("roles", []) if r in Role._value2member_map_)
        return Principal(subject=str(claims["sub"]), roles=roles)


_bearer = HTTPBearer(auto_error=False)


def build_auth_dependencies(
    get_verifier: Callable[..., TokenVerifier],
) -> tuple[
    Callable[..., Coroutine[Any, Any, Principal]],
    Callable[..., Coroutine[Any, Any, Principal]],
]:
    """Return (require_user, require_staff) FastAPI dependencies bound to a verifier provider."""

    async def require_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
        verifier: Annotated[TokenVerifier, Depends(get_verifier)],
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise UnauthorizedError()
        return verifier.verify(credentials.credentials)

    async def require_staff(
        principal: Annotated[Principal, Depends(require_user)],
    ) -> Principal:
        if not principal.is_staff:
            raise ForbiddenError("Staff role required")
        return principal

    return require_user, require_staff


def build_optional_user_dependency(
    get_verifier: Callable[..., TokenVerifier],
) -> Callable[..., Coroutine[Any, Any, Principal | None]]:
    """Dependency for public endpoints that also accept a logged-in user.

    No Authorization header: returns None. A header with an invalid or expired token is
    still rejected with 401, so a client never silently loses its identity.
    """

    async def optional_user(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
        verifier: Annotated[TokenVerifier, Depends(get_verifier)],
    ) -> Principal | None:
        if credentials is None:
            # HTTPBearer ignores other schemes: an Authorization header we cannot use is an error.
            if request.headers.get("Authorization"):
                raise UnauthorizedError()
            return None
        return verifier.verify(credentials.credentials)

    return optional_user
