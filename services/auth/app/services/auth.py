import logging
import uuid
from datetime import timedelta
from typing import Any

from py_common.errors import ConflictError, NotFoundError, UnauthorizedError
from py_common.events import Event, EventPublisher
from py_common.events.auth import UserDeletedV1
from py_common.security import Role

from app.core.security import AccessTokenIssuer, PasswordHasher
from app.models.enums import ConsentPurpose, ConsentSubject
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.auth import ConsentRecordOut, RegisterIn, TokenPair, UserExport, UserOut
from app.services.clock import Clock, utcnow
from app.services.consents import ConsentService
from app.services.tokens import hash_token, new_token

logger = logging.getLogger(__name__)

PRODUCER = "auth"


def _invalid_credentials() -> UnauthorizedError:
    # Same error for unknown email, wrong password and disabled account.
    return UnauthorizedError("Invalid email or password", code="invalid_credentials")


def _invalid_refresh() -> UnauthorizedError:
    return UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")


class AuthService:
    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        issuer: AccessTokenIssuer,
        publisher: EventPublisher,
        refresh_lifetime: timedelta,
        clock: Clock = utcnow,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._issuer = issuer
        self._publisher = publisher
        self._refresh_lifetime = refresh_lifetime
        self._clock = clock
        self._consents = ConsentService(uow, clock)

    async def register(self, data: RegisterIn) -> tuple[User, TokenPair]:
        if await self._uow.users.get_by_email(data.email) is not None:
            raise ConflictError("An account with this email already exists", code="email_taken")
        now = self._clock()
        user = await self._uow.users.add(
            User(
                id=uuid.uuid4(),
                email=data.email,
                password_hash=self._hasher.hash(data.password),
                full_name=data.full_name,
                role=Role.USER,
                is_active=True,
                last_login_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        version = data.consent.privacy_policy_version
        await self._consents.record_user_consent(
            user.id, ConsentPurpose.CONTACT, True, version, data.source
        )
        await self._consents.record_user_consent(
            user.id, ConsentPurpose.MARKETING, data.consent.marketing_accepted, version, data.source
        )
        tokens = await self._issue_tokens(user, family_id=uuid.uuid4())
        await self._uow.commit()
        return user, tokens

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self._uow.users.get_by_email(email)
        valid = self._hasher.verify(user.password_hash if user else None, password)
        if user is None or not valid or not user.is_active:
            raise _invalid_credentials()
        if self._hasher.needs_rehash(user.password_hash):
            user.password_hash = self._hasher.hash(password)
        user.last_login_at = self._clock()
        tokens = await self._issue_tokens(user, family_id=uuid.uuid4())
        await self._uow.commit()
        return tokens

    async def refresh(self, refresh_token: str) -> TokenPair:
        now = self._clock()
        stored = await self._uow.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is None:
            raise _invalid_refresh()
        if stored.revoked_at is not None:
            # A rotated token was used again: someone else may hold it. Revoke the session.
            await self._uow.refresh_tokens.revoke_family(stored.family_id, now)
            await self._uow.commit()
            logger.warning("refresh token reuse detected, session revoked")
            raise UnauthorizedError("Session revoked", code="refresh_token_reused")
        if stored.expires_at <= now:
            raise _invalid_refresh()
        user = await self._uow.users.get(stored.user_id)
        if user is None or not user.is_active:
            await self._uow.refresh_tokens.revoke_family(stored.family_id, now)
            await self._uow.commit()
            raise _invalid_refresh()
        stored.revoked_at = now
        tokens = await self._issue_tokens(user, family_id=stored.family_id)
        await self._uow.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        stored = await self._uow.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is not None:
            await self._uow.refresh_tokens.revoke_family(stored.family_id, self._clock())
            await self._uow.commit()

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._uow.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def export_user(self, user_id: uuid.UUID) -> UserExport:
        user = await self.get_user(user_id)
        history = await self._uow.consents.history(ConsentSubject.USER, user_id)
        return UserExport(
            user=UserOut.model_validate(user),
            consents=[ConsentRecordOut.model_validate(record) for record in history],
            exported_at=self._clock(),
        )

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """GDPR erasure. Other services delete their data on `auth.user_deleted`."""
        user = await self.get_user(user_id)
        if user.role is Role.ADMIN and await self._uow.users.count_active_admins() <= 1:
            raise ConflictError("The last administrator cannot be deleted", code="last_admin")
        await self._uow.consents.delete_for_subject(ConsentSubject.USER, user_id)
        await self._uow.users.delete(user)
        await self._uow.commit()
        await self._emit(UserDeletedV1(user_id=user_id))

    async def _issue_tokens(self, user: User, family_id: uuid.UUID) -> TokenPair:
        now = self._clock()
        refresh_token = new_token()
        await self._uow.refresh_tokens.add(
            RefreshToken(
                id=uuid.uuid4(),
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_token(refresh_token),
                expires_at=now + self._refresh_lifetime,
                created_at=now,
            )
        )
        return TokenPair(
            access_token=self._issuer.issue(user.id, user.role, now),
            refresh_token=refresh_token,
            expires_in=int(self._issuer.lifetime.total_seconds()),
        )

    async def _emit(self, payload: Any) -> None:
        try:
            await self._publisher.publish(Event.wrap(payload, producer=PRODUCER))
        except Exception:
            logger.exception("failed to publish %s", payload.event_type)
