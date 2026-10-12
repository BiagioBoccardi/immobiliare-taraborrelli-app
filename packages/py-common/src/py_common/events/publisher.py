import logging
from typing import Any, Protocol

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection

from py_common.events.base import Event

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, event: Event[Any]) -> None: ...


class InMemoryEventPublisher:
    """Publisher that keeps events in memory. Used in tests and when the broker is disabled."""

    def __init__(self) -> None:
        self.events: list[Event[Any]] = []

    async def publish(self, event: Event[Any]) -> None:
        self.events.append(event)


class RabbitMQEventPublisher:
    """Publishes events to a durable topic exchange, using the routing key `<type>.v<version>`."""

    def __init__(self, url: str, exchange_name: str) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: AbstractRobustConnection | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._exchange = None

    async def publish(self, event: Event[Any]) -> None:
        if self._exchange is None:
            await self.connect()
        assert self._exchange is not None  # noqa: S101
        message = aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
            message_id=str(event.event_id),
            type=event.event_type,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=event.routing_key)
        logger.info("event published", extra={"event_type": event.event_type})
