import uuid
from datetime import UTC, datetime

import pytest
from py_common.errors import ConflictError, NotFoundError
from py_common.pagination import PageParams
from py_common.security import Role

from app.core.security import PasswordHasher
from app.schemas.auth import StaffCreate, UserUpdate
from app.services.users import UserAdminService
from tests.factories import make_refresh_token, make_user, staff_payload
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def service(uow: FakeUnitOfWork) -> UserAdminService:
    return UserAdminService(uow, PasswordHasher(), clock=lambda: NOW)


async def test_create_staff_stores_staff_account(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    user = await service.create_staff(StaffCreate.model_validate(staff_payload()))

    assert uow.users.items[user.id].role is Role.STAFF


async def test_create_staff_with_existing_email_raises_email_taken(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user(email="agente@example.com"))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_staff(StaffCreate.model_validate(staff_payload()))

    assert exc_info.value.code == "email_taken"


async def test_demote_last_admin_raises_last_admin(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    admin = await uow.users.add(make_user(role=Role.ADMIN))

    with pytest.raises(ConflictError) as exc_info:
        await service.update_user(admin.id, UserUpdate(role=Role.STAFF))

    assert exc_info.value.code == "last_admin"


async def test_deactivate_last_admin_raises_last_admin(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    admin = await uow.users.add(make_user(role=Role.ADMIN))

    with pytest.raises(ConflictError):
        await service.update_user(admin.id, UserUpdate(is_active=False))


async def test_demote_admin_when_another_exists_succeeds(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    admin = await uow.users.add(make_user(role=Role.ADMIN))
    await uow.users.add(make_user(role=Role.ADMIN))

    updated = await service.update_user(admin.id, UserUpdate(role=Role.STAFF))

    assert updated.role is Role.STAFF


async def test_deactivate_user_revokes_sessions(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    user = await uow.users.add(make_user())
    token = await uow.refresh_tokens.add(make_refresh_token(user, "t", now=NOW))

    await service.update_user(user.id, UserUpdate(is_active=False))

    assert token.revoked_at == NOW


async def test_rename_user_keeps_sessions(service: UserAdminService, uow: FakeUnitOfWork) -> None:
    user = await uow.users.add(make_user())
    token = await uow.refresh_tokens.add(make_refresh_token(user, "t", now=NOW))

    await service.update_user(user.id, UserUpdate(full_name="Nuovo Nome"))

    assert token.revoked_at is None


async def test_update_unknown_user_raises_not_found(service: UserAdminService) -> None:
    with pytest.raises(NotFoundError):
        await service.update_user(uuid.uuid4(), UserUpdate(is_active=False))


async def test_list_users_filters_by_role(service: UserAdminService, uow: FakeUnitOfWork) -> None:
    await uow.users.add(make_user(role=Role.STAFF))
    await uow.users.add(make_user())

    page = await service.list_users(Role.STAFF, PageParams())

    assert page.total == 1


async def test_create_initial_admin_when_admin_exists_raises_conflict(
    service: UserAdminService, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user(role=Role.ADMIN))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_initial_admin("nuovo@example.com", "Password-lunga-1", "Nuovo Admin")

    assert exc_info.value.code == "admin_exists"


async def test_create_initial_admin_without_admins_creates_admin(
    service: UserAdminService,
) -> None:
    user = await service.create_initial_admin("nuovo@example.com", "Password-lunga-1", "Admin Uno")

    assert user.role is Role.ADMIN
