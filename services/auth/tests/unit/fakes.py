import uuid
from datetime import datetime

from py_common.security import Role

from app.models.consent import ConsentRecord
from app.models.enums import ConsentSubject
from app.models.password_reset import PasswordReset
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.email import Email


class FakeUserRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, User] = {}

    async def add(self, user: User) -> User:
        self.items[user.id] = user
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return self.items.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.items.values() if u.email == email.lower()), None)

    async def list(self, role: Role | None, offset: int, limit: int) -> tuple[list[User], int]:
        users = [u for u in self.items.values() if role is None or u.role == role]
        return users[offset : offset + limit], len(users)

    async def count_active_admins(self) -> int:
        return sum(1 for u in self.items.values() if u.role is Role.ADMIN and u.is_active)

    async def delete(self, user: User) -> None:
        del self.items[user.id]


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.items: list[RefreshToken] = []

    async def add(self, token: RefreshToken) -> RefreshToken:
        self.items.append(token)
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self.items if t.token_hash == token_hash), None)

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        for token in self.items:
            if token.family_id == family_id and token.revoked_at is None:
                token.revoked_at = now

    async def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        for token in self.items:
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now


class FakeConsentRepository:
    def __init__(self) -> None:
        self.items: list[ConsentRecord] = []

    async def add(self, record: ConsentRecord) -> ConsentRecord:
        self.items.append(record)
        return record

    async def add_from_event(self, record: ConsentRecord) -> bool:
        key = (record.source_event_id, record.purpose)
        if any((r.source_event_id, r.purpose) == key for r in self.items):
            return False
        self.items.append(record)
        return True

    async def history(
        self, subject_type: ConsentSubject, subject_id: uuid.UUID
    ) -> list[ConsentRecord]:
        return [
            r for r in self.items if r.subject_type == subject_type and r.subject_id == subject_id
        ]

    async def delete_for_subject(self, subject_type: ConsentSubject, subject_id: uuid.UUID) -> None:
        self.items = [
            r
            for r in self.items
            if not (r.subject_type == subject_type and r.subject_id == subject_id)
        ]


class FakePasswordResetRepository:
    def __init__(self) -> None:
        self.items: list[PasswordReset] = []

    async def add(self, reset: PasswordReset) -> PasswordReset:
        self.items.append(reset)
        return reset

    async def latest_for_user(self, user_id: uuid.UUID) -> PasswordReset | None:
        mine = [r for r in self.items if r.user_id == user_id]
        return max(mine, key=lambda r: r.created_at) if mine else None

    async def close_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        for reset in self.items:
            if reset.user_id == user_id and reset.used_at is None:
                reset.used_at = now


class FakeEmailSender:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[Email] = []
        self.fail = fail

    async def send(self, email: Email) -> None:
        if self.fail:
            raise ConnectionError("smtp down")
        self.sent.append(email)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.refresh_tokens = FakeRefreshTokenRepository()
        self.consents = FakeConsentRepository()
        self.password_resets = FakePasswordResetRepository()
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass
