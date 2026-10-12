"""Personal area: profile, consents, GDPR export and erasure."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import current_user_id, get_auth_service, get_consent_service
from app.schemas.auth import ConsentChange, ConsentStatus, UserExport, UserOut
from app.services.auth import AuthService
from app.services.consents import ConsentService

router = APIRouter(prefix="/me", tags=["me"])

UserId = Annotated[uuid.UUID, Depends(current_user_id)]
Auth = Annotated[AuthService, Depends(get_auth_service)]
Consents = Annotated[ConsentService, Depends(get_consent_service)]


@router.get("", response_model=UserOut)
async def get_me(user_id: UserId, service: Auth) -> UserOut:
    return UserOut.model_validate(await service.get_user(user_id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user_id: UserId, service: Auth) -> Response:
    await service.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export", response_model=UserExport)
async def export_me(user_id: UserId, service: Auth) -> UserExport:
    return await service.export_user(user_id)


@router.get("/consents", response_model=list[ConsentStatus])
async def get_consents(user_id: UserId, service: Consents) -> list[ConsentStatus]:
    return await service.current_for_user(user_id)


@router.post("/consents", response_model=list[ConsentStatus])
async def change_consent(
    user_id: UserId, change: ConsentChange, service: Consents, auth: Auth
) -> list[ConsentStatus]:
    await auth.get_user(user_id)  # the account may have been deleted meanwhile
    return await service.change(user_id, change)
