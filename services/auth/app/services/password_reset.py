""" "Password dimenticata": a 6-digit code sent by email, then a new password."""

import hashlib
import hmac
import logging
import secrets
import uuid
from collections.abc import Callable
from datetime import timedelta

from py_common.email import EmailSender
from py_common.errors import AppError

from app.core.security import PasswordHasher
from app.models.password_reset import PasswordReset
from app.repositories.unit_of_work import UnitOfWork
from app.services.clock import Clock, utcnow
from app.services.email_templates import password_reset_email

logger = logging.getLogger(__name__)

CODE_DIGITS = 6


def _invalid_code() -> AppError:
    # The same error whatever the reason (unknown email, wrong, expired or used code),
    # so the answer never reveals whether an email has an account.
    return AppError("The code is not valid or has expired", code="invalid_reset_code")


def hash_code(user_id: uuid.UUID, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


class PasswordResetService:
    def __init__(
        self,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        sender: EmailSender,
        code_lifetime: timedelta = timedelta(minutes=15),
        max_attempts: int = 5,
        resend_after: timedelta = timedelta(seconds=60),
        clock: Clock = utcnow,
        make_code: Callable[[], str] = new_code,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._sender = sender
        self._lifetime = code_lifetime
        self._max_attempts = max_attempts
        self._resend_after = resend_after
        self._clock = clock
        self._make_code = make_code

    async def request(self, email: str) -> None:
        """Sends a code if the email has an active account. Never says whether it has one."""
        user = await self._uow.users.get_by_email(email)
        if user is None or not user.is_active:
            return
        now = self._clock()
        latest = await self._uow.password_resets.latest_for_user(user.id)
        if latest is not None and latest.created_at > now - self._resend_after:
            return  # one email per minute at most: no email bombing
        await self._uow.password_resets.close_all_for_user(user.id, now)
        code = self._make_code()
        await self._uow.password_resets.add(
            PasswordReset(
                id=uuid.uuid4(),
                user_id=user.id,
                code_hash=hash_code(user.id, code),
                attempts=0,
                expires_at=now + self._lifetime,
                created_at=now,
            )
        )
        await self._uow.commit()
        minutes = int(self._lifetime.total_seconds() // 60)
        try:
            await self._sender.send(password_reset_email(user.email, user.full_name, code, minutes))
        except Exception:
            # The address is not logged; the user can ask for a new code.
            logger.exception("password reset email not sent")

    async def reset(self, email: str, code: str, new_password: str) -> None:
        """Sets the new password and closes every open session of the account."""
        user = await self._uow.users.get_by_email(email)
        if user is None or not user.is_active:
            raise _invalid_code()
        now = self._clock()
        reset = await self._uow.password_resets.latest_for_user(user.id)
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise _invalid_code()
        if not hmac.compare_digest(reset.code_hash, hash_code(user.id, code)):
            reset.attempts += 1
            if reset.attempts >= self._max_attempts:
                reset.used_at = now  # too many wrong codes: a new one must be requested
            await self._uow.commit()
            raise _invalid_code()
        reset.used_at = now
        user.password_hash = self._hasher.hash(new_password)
        user.updated_at = now
        await self._uow.refresh_tokens.revoke_all_for_user(user.id, now)
        await self._uow.commit()
