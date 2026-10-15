from collections.abc import Callable
from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from py_common.errors import UnauthorizedError, register_error_handlers
from py_common.security import (
    Principal,
    Role,
    TokenVerifier,
    build_auth_dependencies,
    build_optional_user_dependency,
)


def test_verify_valid_staff_token_returns_staff_principal(
    verifier: TokenVerifier, make_token: Callable[..., str]
) -> None:
    token = make_token(roles=["staff"])

    principal = verifier.verify(token)

    assert principal.subject == "user-1"
    assert principal.roles == frozenset({Role.STAFF})
    assert principal.is_staff


def test_verify_token_with_unknown_role_ignores_it(
    verifier: TokenVerifier, make_token: Callable[..., str]
) -> None:
    token = make_token(roles=["user", "superhero"])

    principal = verifier.verify(token)

    assert principal.roles == frozenset({Role.USER})
    assert not principal.is_staff


def test_verify_expired_token_raises_token_expired(
    verifier: TokenVerifier, make_token: Callable[..., str]
) -> None:
    token = make_token(expires_in=timedelta(minutes=-1))

    with pytest.raises(UnauthorizedError) as exc_info:
        verifier.verify(token)

    assert exc_info.value.code == "token_expired"


def test_verify_token_with_wrong_audience_raises_invalid_token(
    verifier: TokenVerifier, make_token: Callable[..., str]
) -> None:
    token = make_token(aud="someone-else")

    with pytest.raises(UnauthorizedError) as exc_info:
        verifier.verify(token)

    assert exc_info.value.code == "invalid_token"


def test_verify_without_public_key_raises_unauthorized(make_token: Callable[..., str]) -> None:
    verifier = TokenVerifier("", "RS256", "taraborrelli", "taraborrelli-auth")

    with pytest.raises(UnauthorizedError):
        verifier.verify(make_token())


@pytest.fixture
def secured_app(verifier: TokenVerifier) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    _, require_staff = build_auth_dependencies(lambda: verifier)

    @app.get("/staff-only")
    async def staff_only(principal: Annotated[Principal, Depends(require_staff)]) -> dict[str, str]:
        return {"sub": principal.subject}

    return app


async def _get(app: FastAPI, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/staff-only", headers=headers or {})
    return response.status_code, response.json()


async def test_staff_endpoint_without_token_returns_401(secured_app: FastAPI) -> None:
    status, body = await _get(secured_app)

    assert status == 401
    assert body["code"] == "unauthorized"


async def test_staff_endpoint_with_user_role_returns_403(
    secured_app: FastAPI, make_token: Callable[..., str]
) -> None:
    status, body = await _get(
        secured_app, {"Authorization": f"Bearer {make_token(roles=['user'])}"}
    )

    assert status == 403
    assert body["code"] == "forbidden"


async def test_staff_endpoint_with_admin_role_returns_200(
    secured_app: FastAPI, make_token: Callable[..., str]
) -> None:
    status, body = await _get(
        secured_app, {"Authorization": f"Bearer {make_token(roles=['admin'])}"}
    )

    assert status == 200
    assert body == {"sub": "user-1"}


@pytest.fixture
def optional_app(verifier: TokenVerifier) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    optional_user = build_optional_user_dependency(lambda: verifier)

    @app.get("/form")
    async def form(
        principal: Annotated[Principal | None, Depends(optional_user)],
    ) -> dict[str, str]:
        return {"sub": principal.subject if principal else "anonymous"}

    return app


async def _get_form(app: FastAPI, headers: dict[str, str] | None = None) -> tuple[int, object]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/form", headers=headers or {})
    return response.status_code, response.json()


async def test_optional_user_without_token_is_anonymous(optional_app: FastAPI) -> None:
    status, body = await _get_form(optional_app)

    assert (status, body) == (200, {"sub": "anonymous"})


async def test_optional_user_with_valid_token_is_identified(
    optional_app: FastAPI, make_token: Callable[..., str]
) -> None:
    status, body = await _get_form(optional_app, {"Authorization": f"Bearer {make_token()}"})

    assert (status, body) == (200, {"sub": "user-1"})


async def test_optional_user_with_invalid_token_returns_401(optional_app: FastAPI) -> None:
    status, _ = await _get_form(optional_app, {"Authorization": "Bearer not-a-token"})

    assert status == 401


async def test_optional_user_with_other_scheme_returns_401(optional_app: FastAPI) -> None:
    status, _ = await _get_form(optional_app, {"Authorization": "Basic abc"})

    assert status == 401
