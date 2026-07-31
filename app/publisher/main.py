import asyncio
import json

import aio_pika
from sqlalchemy import select

from app.core.config import settings
from app.core.db import async_session_factory
from app.models.outbox import OutboxEvent


async def publish_events(channel: aio_pika.Channel):
    async with async_session_factory() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published == False)
            .order_by(OutboxEvent.created_at)
            .limit(settings.OUTBOX_BATCH_SIZE)
        )
        events = result.scalars().all()

        for event in events:
            await publish_single(channel, event)
            event.published = True

        if events:
            await session.commit()


async def publish_single(channel: aio_pika.Channel, event: OutboxEvent):
    exchange = await channel.get_exchange(settings.EXCHANGE_NAME, ensure=True)
    message = aio_pika.Message(
        body=json.dumps(event.payload).encode(),
        content_type="application/json",
        message_id=str(event.id),
        headers={"x-retry-count": 0},
    )
    await exchange.publish(message, routing_key=settings.ROUTING_KEY)


async def run_publisher():
    while True:
        try:
            connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL, reconnect_interval=5
            )
            async with connection:
                channel = await connection.channel()

                await channel.declare_exchange(
                    settings.EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                while True:
                    try:
                        await publish_events(channel)
                    except Exception as e:
                        print(f"Publisher error: {e}")

                    await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)
        except Exception as e:
            print(f"Publisher connection error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_publisher())
