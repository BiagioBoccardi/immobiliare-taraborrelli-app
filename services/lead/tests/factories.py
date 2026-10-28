"""Valid test data. Never real personal data."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.enums import (
    LeadKind,
    LeadPriority,
    LeadStatus,
    OwnerIntention,
    PropertyCondition,
    PropertyType,
)
from app.models.lead import Lead
from app.services.tokens import hash_token


def consent_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "privacy_accepted": True,
        "privacy_policy_version": "2026-01",
        "marketing_accepted": False,
    }
    data.update(overrides)
    return data


def valuation_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "full_name": "Mario Rossi",
        "phone": "+39 333 000 0000",
        "municipality": "Chieti",
        "property_type": "apartment",
        "surface_sqm": 95,
        "rooms": 4,
        "condition": "good",
        "intention": "planning",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def owner_request_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": "sell",
        "full_name": "Anna Bianchi",
        "phone": "333 111 2222",
        "municipality": "Chieti Scalo",
        "property_type": "house",
        "intention": "decided",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def callback_request_payload(**overrides: Any) -> dict[str, Any]:
    """The website's "Richiedi di essere ricontattato" form."""
    data: dict[str, Any] = {
        "first_name": "Luca",
        "last_name": "Neri",
        "email": "luca.neri@example.com",
        "phone": "+39 333 444 5555",
        "preferred_time": "morning",
        "message": "Cerco un bilocale a Chieti Scalo.",
        "consent": consent_payload(),
    }
    data.update(overrides)
    return data


def make_lead(
    *,
    token: str | None = None,
    created_at: datetime | None = None,
    **overrides: Any,
) -> Lead:
    now = created_at or datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "kind": LeadKind.VALUATION,
        "status": LeadStatus.NEW,
        "priority": LeadPriority.MEDIUM,
        "intention": OwnerIntention.PLANNING,
        "full_name": "Mario Rossi",
        "phone": "+393330000000",
        "municipality": "Chieti",
        "property_type": PropertyType.APARTMENT,
        "surface_sqm": 95,
        "rooms": 4,
        "condition": PropertyCondition.GOOD,
        "details": {},
        "completion_token_hash": hash_token(token) if token else None,
        "contact_consent_at": now,
        "privacy_policy_version": "2026-01",
        "marketing_consent": False,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Lead(**values)
