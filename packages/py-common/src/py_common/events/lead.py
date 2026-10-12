"""Events emitted by the lead service.

Payloads carry identifiers and non-personal attributes only: consumers that need contact
data must read it through the lead service API with the proper permissions.
"""

import uuid
from datetime import datetime
from typing import Literal

from py_common.events.base import EventPayload

LeadKind = Literal["valuation", "sell", "rent"]
LeadPriority = Literal["low", "medium", "high"]


class ValuationRequestedV1(EventPayload):
    event_type = "lead.valuation_requested"
    version = 1

    lead_id: uuid.UUID
    priority: LeadPriority
    municipality: str
    property_type: str


class OwnerRequestReceivedV1(EventPayload):
    """A "Voglio vendere casa" or "Voglio affittare il mio immobile" request was received."""

    event_type = "lead.owner_request_received"
    version = 1

    lead_id: uuid.UUID
    kind: Literal["sell", "rent"]
    priority: LeadPriority
    municipality: str
    property_type: str


class LeadConsentGivenV1(EventPayload):
    """Consents given by an owner when submitting a form, to be stored in the auth registry."""

    event_type = "lead.consent_given"
    version = 1

    lead_id: uuid.UUID
    policy_version: str
    purposes: tuple[Literal["contact", "marketing"], ...]
    given_at: datetime
