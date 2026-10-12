import asyncio
import uuid
from collections.abc import Callable, Iterator

import aio_pika
import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer

from py_common.events import Event, RabbitMQConsumer, RabbitMQEventPublisher
from py_common.events.auth import UserDeletedV1

pytestmark = pytest.mark.integration

EXCHANGE = "test.consumer.events"


@pytest.fixture(scope="module")
def rabbitmq_url() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:3.13-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(container.port)
        yield f"amqp://guest:guest@{host}:{port}/"


def _event() -> Event[UserDeletedV1]:
    return Event.wrap(UserDeletedV1(user_id=uuid.uuid4()), producer="auth")


async def _wait_for(condition: Callable[[], object], attempts: int = 50) -> None:
    for _ in range(attempts):
        if condition():
            return
        await asyncio.sleep(0.1)


async def test_consumer_passes_matching_events_to_handler(rabbitmq_url: str) -> None:
    received: list[tuple[str, bytes]] = []

    async def handler(routing_key: str, body: bytes) -> None:
        received.append((routing_key, body))

    consumer = RabbitMQConsumer(
        rabbitmq_url, EXCHANGE, "test.ok", ["auth.user_deleted.v1"], handler
    )
    await consumer.start()
    publisher = RabbitMQEventPublisher(rabbitmq_url, EXCHANGE)
    event = _event()

    await publisher.publish(event)

    await _wait_for(lambda: received)
    await publisher.close()
    await consumer.stop()
    assert received[0][0] == "auth.user_deleted.v1"
    assert Event[UserDeletedV1].model_validate_json(received[0][1]) == event


async def test_consumer_moves_failing_message_to_dead_letter_queue(rabbitmq_url: str) -> None:
    async def handler(routing_key: str, body: bytes) -> None:
        raise ValueError("cannot process")

    consumer = RabbitMQConsumer(
        rabbitmq_url, EXCHANGE, "test.failing", ["auth.user_deleted.v1"], handler
    )
    await consumer.start()
    publisher = RabbitMQEventPublisher(rabbitmq_url, EXCHANGE)

    await publisher.publish(_event())

    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    dead_queue = await channel.declare_queue("test.failing.dead", durable=True)
    message = None
    for _ in range(50):
        message = await dead_queue.get(no_ack=True, fail=False)
        if message is not None:
            break
        await asyncio.sleep(0.1)
    await connection.close()
    await publisher.close()
    await consumer.stop()
    assert message is not None


async def test_start_in_background_retries_until_broker_is_reachable(rabbitmq_url: str) -> None:
    received: list[str] = []

    async def handler(routing_key: str, body: bytes) -> None:
        received.append(routing_key)

    # The first attempts target a closed port; then the broker becomes reachable.
    consumer = RabbitMQConsumer(
        "amqp://guest:guest@127.0.0.1:1/", EXCHANGE, "test.retry", ["auth.#"], handler
    )
    consumer.start_in_background(max_delay=0.2)
    await asyncio.sleep(0.3)
    consumer._url = rabbitmq_url
    await _wait_for(lambda: consumer._task is not None and consumer._task.done())
    publisher = RabbitMQEventPublisher(rabbitmq_url, EXCHANGE)

    await publisher.publish(_event())

    await _wait_for(lambda: received)
    await publisher.close()
    await consumer.stop()
    assert received == ["auth.user_deleted.v1"]


async def test_stop_cancels_pending_background_start() -> None:
    async def handler(routing_key: str, body: bytes) -> None:
        return None

    consumer = RabbitMQConsumer("amqp://guest:guest@127.0.0.1:1/", EXCHANGE, "q", ["#"], handler)
    consumer.start_in_background()
    await asyncio.sleep(0.1)

    await consumer.stop()

    assert consumer._task is None
