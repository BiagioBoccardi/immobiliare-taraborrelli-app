import logging

from py_common.events import Event
from py_common.events.lead import LeadConsentGivenV1
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.unit_of_work import SqlUnitOfWork
from app.services.consents import ConsentService

logger = logging.getLogger(__name__)

LEAD_CONSENT_ROUTING_KEY = "lead.consent_given.v1"


class LeadConsentHandler:
    """Stores consents given on lead forms. Safe to receive the same event twice."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self, routing_key: str, body: bytes) -> None:
        event = Event[LeadConsentGivenV1].model_validate_json(body)
        async with self._session_factory() as session:
            inserted = await ConsentService(SqlUnitOfWork(session)).record_lead_consent(event)
        if inserted == 0:
            logger.info("duplicate lead consent event ignored")
