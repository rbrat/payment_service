import asyncio
import json
import random
from datetime import datetime, timezone

import aio_pika
from sqlalchemy import select

from app.core.config import settings
from app.core.db import async_session_factory
from app.models.payment import Payment
from app.schemas.payment import WebhookPayload, PaymentStatusEnum
from app.services.webhook import send_webhook


async def setup_topology(channel: aio_pika.Channel):
    exchange = await channel.declare_exchange(
        settings.EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    dlq = await channel.declare_queue(settings.DLQ_NAME, durable=True)
    await dlq.bind(exchange, routing_key=settings.DLQ_NAME)

    for queue_name, ttl in zip(settings.RETRY_QUEUES, settings.RETRY_DELAYS_MS):
        retry_queue = await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-message-ttl": ttl,
                "x-dead-letter-exchange": settings.EXCHANGE_NAME,
                "x-dead-letter-routing-key": settings.ROUTING_KEY,
            },
        )
        await retry_queue.bind(exchange, routing_key=queue_name)

    main_queue = await channel.declare_queue(
        settings.QUEUE_NAME,
        durable=True,
    )
    await main_queue.bind(exchange, routing_key=settings.ROUTING_KEY)

    return exchange, main_queue, dlq


async def process_payment(payment_id: str) -> tuple[bool, str | None]:
    delay = random.uniform(settings.PROCESSING_DELAY_MIN, settings.PROCESSING_DELAY_MAX)
    await asyncio.sleep(delay)
    success = random.random() < settings.SUCCESS_RATE
    if success:
        return True, None
    return False, "Payment processing error"


async def handle_message(message: aio_pika.IncomingMessage, channel: aio_pika.Channel):
    retry_count = 0
    if message.headers:
        retry_count = int(message.headers.get("x-retry-count", 0))

    body = json.loads(message.body.decode())
    payment_id = body.get("payment_id")
    webhook_url = body.get("webhook_url")

    if not payment_id:
        await message.ack()
        return

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            payment = result.scalar_one_or_none()

            if not payment:
                await message.ack()
                return

            if retry_count == 0:
                success, error = await process_payment(payment_id)
                payment.status = (
                    PaymentStatusEnum.succeeded.value if success else PaymentStatusEnum.failed.value
                )
                payment.error_message = error
                payment.processed_at = datetime.now(timezone.utc)
                await session.commit()

            webhook_payload = WebhookPayload(
                payment_id=payment.id,
                status=PaymentStatusEnum(payment.status),
                error_message=payment.error_message,
            )
            webhook_ok = await send_webhook(webhook_url, webhook_payload)

            if not webhook_ok:
                raise RuntimeError("Webhook delivery failed")

        await message.ack()

    except Exception:
        await retry_or_dlq(message, channel, retry_count)


async def retry_or_dlq(
    message: aio_pika.IncomingMessage,
    channel: aio_pika.Channel,
    retry_count: int,
):
    next_retry = retry_count + 1
    exchange = await channel.get_exchange(settings.EXCHANGE_NAME, ensure=True)

    if next_retry > settings.MAX_RETRIES:
        dlq_message = aio_pika.Message(
            body=message.body,
            content_type="application/json",
            headers={
                "x-retry-count": next_retry,
                "x-original-routing-key": message.routing_key,
            },
        )
        await exchange.publish(dlq_message, routing_key=settings.DLQ_NAME)
        await message.ack()
    else:
        retry_queue_name = settings.RETRY_QUEUES[next_retry - 1]
        retry_msg = aio_pika.Message(
            body=message.body,
            content_type="application/json",
            headers={"x-retry-count": next_retry},
        )
        await exchange.publish(retry_msg, routing_key=retry_queue_name)
        await message.ack()


async def run_consumer():
    while True:
        try:
            connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL, reconnect_interval=5
            )
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)

                _, main_queue, _ = await setup_topology(channel)

                async with main_queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await handle_message(message, channel)
        except Exception as e:
            print(f"Consumer error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_consumer())
