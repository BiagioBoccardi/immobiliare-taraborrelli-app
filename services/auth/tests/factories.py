"""Valid test data. Never real personal data."""

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from py_common.events import Event
from py_common.events.lead import LeadConsentGivenV1
from py_common.security import Role

from app.core.security import PasswordHasher
from app.models.consent import ConsentRecord
from app.models.enums import ConsentPurpose, ConsentSource, ConsentSubject
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.tokens import hash_token

DEFAULT_PASSWORD = "Password-di-prova-1"


@lru_cache
def default_password_hash() -> str:
    return PasswordHasher().hash(DEFAULT_PASSWORD)


def register_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "email": "Mario.Rossi@Example.com",
        "password": DEFAULT_PASSWORD,
        "full_name": "Mario Rossi",
        "consent": {
            "privacy_accepted": True,
            "privacy_policy_version": "2026-01",
            "marketing_accepted": False,
        },
    }
    data.update(overrides)
    return data


def staff_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "email": "agente@example.com",
        "password": DEFAULT_PASSWORD,
        "full_name": "Laura Agente",
        "role": "staff",
    }
    data.update(overrides)
    return data


def make_user(**overrides: Any) -> User:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "email": f"utente-{uuid.uuid4().hex[:8]}@example.com",
        "password_hash": default_password_hash(),
        "full_name": "Utente Prova",
        "role": Role.USER,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return User(**values)


def make_refresh_token(
    user: User, token: str, *, now: datetime | None = None, **overrides: Any
) -> RefreshToken:
    now = now or datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "family_id": uuid.uuid4(),
        "token_hash": hash_token(token),
        "expires_at": now + timedelta(days=30),
        "created_at": now,
    }
    values.update(overrides)
    return RefreshToken(**values)


def make_consent(subject_id: uuid.UUID, **overrides: Any) -> ConsentRecord:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "subject_type": ConsentSubject.USER,
        "subject_id": subject_id,
        "purpose": ConsentPurpose.CONTACT,
        "granted": True,
        "policy_version": "2026-01",
        "source": ConsentSource.APP,
        "recorded_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ConsentRecord(**values)


def lead_consent_event(
    purposes: tuple[str, ...] = ("contact", "marketing"),
) -> Event[LeadConsentGivenV1]:
    return Event.wrap(
        LeadConsentGivenV1.model_validate(
            {
                "lead_id": str(uuid.uuid4()),
                "policy_version": "2026-01",
                "purposes": purposes,
                "given_at": datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
            }
        ),
        producer="lead",
    )
