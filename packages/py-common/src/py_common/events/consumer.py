"""RabbitMQ consumer with a dead-letter queue for messages that cannot be processed."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Sequence

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, bytes], Awaitable[None]]


class RabbitMQConsumer:
    """Consumes `routing_keys` from the events exchange into a durable queue.

    The handler receives (routing_key, body). If it raises, the message is rejected and
    moved to `<queue>.dead` so it can be inspected instead of being retried forever.
    Handlers must be idempotent: RabbitMQ delivers at least once.
    """

    def __init__(
        self,
        url: str,
        exchange_name: str,
        queue_name: str,
        routing_keys: Sequence[str],
        handler: MessageHandler,
        prefetch: int = 10,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._routing_keys = routing_keys
        self._handler = handler
        self._prefetch = prefetch
        self._connection: AbstractRobustConnection | None = None
        self._task: asyncio.Task[None] | None = None

    def start_in_background(self, max_delay: float = 30.0) -> None:
        """Connects without blocking startup, retrying with backoff while the broker is down.

        The service keeps answering HTTP requests even when RabbitMQ is unavailable.
        """

        async def _run() -> None:
            delay = 1.0
            while True:
                try:
                    await self.start()
                except Exception:
                    logger.warning("broker unavailable, retrying in %.1fs", delay)
                    await self._close_connection()
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay)
                else:
                    logger.info("consuming from %s", self._queue_name)
                    return

        self._task = asyncio.create_task(_run())

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=self._prefetch)
        exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dead_letter_exchange = await channel.declare_exchange(
            f"{self._exchange_name}.dead", aio_pika.ExchangeType.DIRECT, durable=True
        )
        dead_queue = await channel.declare_queue(f"{self._queue_name}.dead", durable=True)
        await dead_queue.bind(dead_letter_exchange, routing_key=self._queue_name)
        queue = await channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{self._exchange_name}.dead",
                "x-dead-letter-routing-key": self._queue_name,
            },
        )
        for routing_key in self._routing_keys:
            await queue.bind(exchange, routing_key=routing_key)
        await queue.consume(self._on_message)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._close_connection()

    async def _close_connection(self) -> None:
        if self._connection is not None:
            with contextlib.suppress(Exception):
                await self._connection.close()
        self._connection = None

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            await self._handler(message.routing_key or "", message.body)
        except Exception:
            logger.exception("event handling failed, moved to dead-letter queue")
            await message.reject(requeue=False)
        else:
            await message.ack()
