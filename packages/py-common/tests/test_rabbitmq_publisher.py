import asyncio
import uuid
from collections.abc import Iterator

import aio_pika
import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer

from py_common.events import Event, RabbitMQEventPublisher
from py_common.events.lead import ValuationRequestedV1

pytestmark = pytest.mark.integration

EXCHANGE = "test.events"


@pytest.fixture(scope="module")
def rabbitmq_url() -> Iterator[str]:
    with RabbitMqContainer("rabbitmq:3.13-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(container.port)
        yield f"amqp://guest:guest@{host}:{port}/"


async def test_publish_delivers_event_with_versioned_routing_key(rabbitmq_url: str) -> None:
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(exclusive=True)
    await queue.bind(exchange, routing_key="lead.#")
    publisher = RabbitMQEventPublisher(rabbitmq_url, EXCHANGE)
    event = Event.wrap(
        ValuationRequestedV1(
            lead_id=uuid.uuid4(), priority="high", municipality="Chieti", property_type="house"
        ),
        producer="lead",
    )

    await publisher.publish(event)

    message = None
    for _ in range(50):
        message = await queue.get(no_ack=True, fail=False)
        if message is not None:
            break
        await asyncio.sleep(0.1)
    await publisher.close()
    await connection.close()
    assert message is not None
    assert message.routing_key == "lead.valuation_requested.v1"
    assert message.message_id == str(event.event_id)
    assert Event[ValuationRequestedV1].model_validate_json(message.body) == event
