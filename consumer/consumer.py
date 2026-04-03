
import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone

import aio_pika
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.core.config import settings


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False)


async def emulate_payment_gateway() -> bool:
    """90% success, 10% failure, 2-5 sec delay"""
    delay = random.uniform(2, 5)
    await asyncio.sleep(delay)
    return random.random() < 0.9


async def send_webhook(webhook_url: str, payload: dict, attempt: int = 0) -> bool:
    backoff = 2 ** attempt
    await asyncio.sleep(backoff)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            return response.status_code < 400
    except Exception as e:
        logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
        return False


async def process_payment_message(body: bytes, db: AsyncSession):
    data = json.loads(body)
    payment_id = uuid.UUID(data["payment_id"])
    webhook_url = data.get("webhook_url")

    # Get payment
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        logger.error(f"Payment {payment_id} not found")
        return

    if payment.status != "pending":
        logger.info(
            f"Payment {payment_id} already processed with status {payment.status}")
        return

    # Emulate processing
    success = await emulate_payment_gateway()
    new_status = "succeeded" if success else "failed"

    await db.execute(
        update(Payment)
        .where(Payment.id == payment_id)
        .values(status=new_status, processed_at=datetime.now(timezone.utc))
    )
    await db.commit()
    logger.info(f"Payment {payment_id} -> {new_status}")

    # Send webhook with retries
    if webhook_url:
        webhook_payload = {
            "payment_id": str(payment_id),
            "status": new_status,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        for attempt in range(settings.WEBHOOK_RETRY_ATTEMPTS):
            ok = await send_webhook(webhook_url, webhook_payload, attempt)
            if ok:
                logger.info(f"Webhook sent for payment {payment_id}")
                break
        else:
            logger.error(
                f"All webhook attempts failed for payment {payment_id}")


async def outbox_publisher(channel: aio_pika.Channel):
    """Periodically publishes unpublished outbox events to RabbitMQ"""
    exchange = await channel.declare_exchange(
        settings.PAYMENT_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True
    )
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published == False)
                    .limit(10)
                )
                events = result.scalars().all()
                for event in events:
                    msg = aio_pika.Message(
                        body=json.dumps(event.payload).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        message_id=str(event.id),
                    )
                    await exchange.publish(msg, routing_key=settings.PAYMENT_QUEUE)
                    event.published = True
                    event.published_at = datetime.now(timezone.utc)
                await db.commit()
                if events:
                    logger.info(f"Published {len(events)} outbox events")
        except Exception as e:
            logger.error(f"Outbox publisher error: {e}")
        await asyncio.sleep(1)


async def main():
    logger.info("Starting consumer...")

    # Wait for RabbitMQ
    for i in range(30):
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            break
        except Exception:
            logger.info(f"Waiting for RabbitMQ... ({i+1}/30)")
            await asyncio.sleep(2)
    else:
        logger.error("Could not connect to RabbitMQ")
        return

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)

        # Declare DLQ exchange and queue
        dlx_exchange = await channel.declare_exchange(
            "payments.dlx", aio_pika.ExchangeType.DIRECT, durable=True
        )
        dlq = await channel.declare_queue(
            settings.PAYMENT_DLQ,
            durable=True,
        )
        await dlq.bind(dlx_exchange, routing_key=settings.PAYMENT_DLQ)

        # Declare main exchange and queue with DLX
        exchange = await channel.declare_exchange(
            settings.PAYMENT_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True
        )
        queue = await channel.declare_queue(
            settings.PAYMENT_QUEUE,
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": "payments.dlx",
                "x-dead-letter-routing-key": settings.PAYMENT_DLQ,
                "x-message-ttl": 60000,
                "x-delivery-limit": 3,
            },
        )
        await queue.bind(exchange, routing_key=settings.PAYMENT_QUEUE)

        # Start outbox publisher in background
        asyncio.create_task(outbox_publisher(channel))

        logger.info("Consumer ready, waiting for messages...")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    async with AsyncSessionLocal() as db:
                        await process_payment_message(message.body, db)
                    await message.ack()
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    delivery_count = message.headers.get(
                        "x-delivery-count", 0) if message.headers else 0
                    if delivery_count >= 2:
                        logger.error(
                            f"Sending to DLQ after {delivery_count + 1} attempts")
                        await message.reject(requeue=False)
                    else:
                        await message.nack(requeue=True)


if __name__ == "__main__":
    asyncio.run(main())
