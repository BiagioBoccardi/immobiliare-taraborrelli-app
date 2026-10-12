"""Account management for the admin panel. Requires the admin role."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from py_common.pagination import Page, PageParams, page_params
from py_common.security import Role

from app.core.dependencies import get_user_admin_service, require_admin
from app.schemas.auth import StaffCreate, UserOut, UserUpdate
from app.services.users import UserAdminService

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])

Service = Annotated[UserAdminService, Depends(get_user_admin_service)]


@router.get("", response_model=Page[UserOut])
async def list_users(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    role: Role | None = None,
) -> Page[UserOut]:
    return await service.list_users(role, params)


@router.post("/staff", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_staff(data: StaffCreate, service: Service) -> UserOut:
    return UserOut.model_validate(await service.create_staff(data))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, changes: UserUpdate, service: Service) -> UserOut:
    return UserOut.model_validate(await service.update_user(user_id, changes))
