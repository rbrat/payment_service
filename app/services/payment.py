from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.schemas.payment import CurrencyEnum


async def get_payment_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> Payment | None:
    result = await session.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def get_payment_by_id(session: AsyncSession, payment_id: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def create_payment(
    session: AsyncSession,
    amount: Decimal,
    currency: CurrencyEnum,
    description: str,
    metadata: dict,
    webhook_url: str,
    idempotency_key: str,
) -> Payment:
    payment = Payment(
        amount=amount,
        currency=currency.value,
        description=description,
        payment_metadata=metadata,
        webhook_url=webhook_url,
        idempotency_key=idempotency_key,
        status="pending",
    )
    session.add(payment)
    await session.flush()

    outbox_event = OutboxEvent(
        aggregate_type="payment",
        aggregate_id=str(payment.id),
        event_type="payment.created",
        payload={
            "payment_id": str(payment.id),
            "amount": str(amount),
            "currency": currency.value,
            "description": description,
            "webhook_url": webhook_url,
        },
    )
    session.add(outbox_event)

    await session.commit()
    return payment
