"""Public authentication endpoints (rate limited at the gateway)."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import PlainTextResponse
from py_common.security import TokenVerifier

from app.core.dependencies import get_auth_service, get_password_reset_service
from app.schemas.auth import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenPair,
)
from app.services.auth import AuthService
from app.services.password_reset import PasswordResetService

router = APIRouter(tags=["auth"])

Service = Annotated[AuthService, Depends(get_auth_service)]
ResetService = Annotated[PasswordResetService, Depends(get_password_reset_service)]


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenPair)
async def register(data: RegisterIn, service: Service) -> TokenPair:
    _, tokens = await service.register(data)
    return tokens


@router.post("/login", response_model=TokenPair)
async def login(data: LoginIn, service: Service) -> TokenPair:
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshIn, service: Service) -> TokenPair:
    return await service.refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshIn, service: Service) -> Response:
    await service.logout(data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(data: ForgotPasswordIn, service: ResetService) -> Response:
    """Emails a code to reset the password. Same answer whether or not the email exists."""
    await service.request(data.email)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: ResetPasswordIn, service: ResetService) -> Response:
    await service.reset(data.email, data.code, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public-key", response_class=PlainTextResponse)
async def public_key(request: Request) -> str:
    """PEM public key that other services use to verify access tokens."""
    return cast(TokenVerifier, request.app.state.token_verifier).public_key
