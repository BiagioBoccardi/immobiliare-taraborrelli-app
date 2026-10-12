import logging
from typing import Any

from py_common.events import Event

logger = logging.getLogger(__name__)


class LoggingEventPublisher:
    """Fallback used when events are disabled: logs the event type only, never the payload."""

    async def publish(self, event: Event[Any]) -> None:
        logger.info("event not sent (events disabled): %s", event.event_type)
