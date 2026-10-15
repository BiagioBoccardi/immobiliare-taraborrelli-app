import logging
from datetime import timedelta

from py_common.events import Event, InMemoryEventPublisher
from py_common.events.auth import UserDeletedV1
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.lead import SqlLeadRepository
from app.services.lead import LeadService

logger = logging.getLogger(__name__)

USER_DELETED_ROUTING_KEY = "auth.user_deleted.v1"


class UserDeletedHandler:
    """Deletes the requests linked to an account the user erased. Safe to receive twice."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self, routing_key: str, body: bytes) -> None:
        event = Event[UserDeletedV1].model_validate_json(body)
        async with self._session_factory() as session:
            # Deleting emits no events and has nothing to do with the completion window.
            service = LeadService(
                SqlLeadRepository(session), InMemoryEventPublisher(), timedelta(0)
            )
            deleted = await service.delete_user_requests(event.payload.user_id)
        logger.info("deleted %d requests of an erased account", deleted)
