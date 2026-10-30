"""Notice to the agency when a new request arrives ("Nuova richiesta dal sito / dall'app")."""

import logging
from typing import Protocol

from py_common.email import Email, EmailSender

from app.models.lead import Lead
from app.services.email_templates import new_lead_email

logger = logging.getLogger(__name__)


class StaffNotifier(Protocol):
    async def new_lead(self, lead: Lead) -> None: ...


class NoStaffNotifier:
    """Used when no recipient is configured: nothing is sent."""

    async def new_lead(self, lead: Lead) -> None:
        return None


class EmailStaffNotifier:
    def __init__(self, sender: EmailSender, recipients: list[str], admin_url: str) -> None:
        self._sender = sender
        self._recipients = recipients
        self._admin_url = admin_url.rstrip("/")

    async def new_lead(self, lead: Lead) -> None:
        link = f"{self._admin_url}/leads/{lead.id}" if self._admin_url else ""
        for recipient in self._recipients:
            email: Email = new_lead_email(recipient, lead, link)
            await self._sender.send(email)
        logger.info("staff notified of a new lead", extra={"lead_id": str(lead.id)})
