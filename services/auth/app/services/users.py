import uuid

from py_common.errors import ConflictError, NotFoundError
from py_common.pagination import Page, PageParams
from py_common.security import Role

from app.core.security import PasswordHasher
from app.models.user import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.auth import StaffCreate, UserOut, UserUpdate
from app.services.clock import Clock, utcnow


class UserAdminService:
    """Account management for administrators (agency staff accounts, roles, deactivation)."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock = utcnow) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def create_staff(self, data: StaffCreate) -> User:
        if await self._uow.users.get_by_email(data.email) is not None:
            raise ConflictError("An account with this email already exists", code="email_taken")
        now = self._clock()
        user = await self._uow.users.add(
            User(
                id=uuid.uuid4(),
                email=data.email,
                password_hash=self._hasher.hash(data.password),
                full_name=data.full_name,
                role=Role(data.role),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await self._uow.commit()
        return user

    async def list_users(self, role: Role | None, params: PageParams) -> Page[UserOut]:
        users, total = await self._uow.users.list(role, params.offset, params.size)
        return Page[UserOut](
            items=[UserOut.model_validate(user) for user in users],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def update_user(self, user_id: uuid.UUID, changes: UserUpdate) -> User:
        user = await self._uow.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        data = changes.model_dump(exclude_unset=True, exclude_none=True)
        loses_admin = (
            user.role is Role.ADMIN
            and user.is_active
            and (data.get("role", Role.ADMIN) is not Role.ADMIN or data.get("is_active") is False)
        )
        if loses_admin and await self._uow.users.count_active_admins() <= 1:
            raise ConflictError("At least one active administrator is required", code="last_admin")
        role_changed = "role" in data and data["role"] is not user.role
        for field, value in data.items():
            setattr(user, field, value)
        user.updated_at = self._clock()
        if role_changed or data.get("is_active") is False:
            # Existing sessions end: the next login issues tokens with the new permissions.
            await self._uow.refresh_tokens.revoke_all_for_user(user.id, self._clock())
        await self._uow.commit()
        return user

    async def create_initial_admin(self, email: str, password: str, full_name: str) -> User:
        """Bootstrap from the command line: only allowed while no administrator exists."""
        if await self._uow.users.count_active_admins() > 0:
            raise ConflictError("An administrator already exists", code="admin_exists")
        return await self.create_staff(
            StaffCreate(email=email, password=password, full_name=full_name, role=Role.ADMIN)
        )
