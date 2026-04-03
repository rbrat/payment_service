import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.payment import Payment
from app.models.outbox import OutboxEvent
from app.schemas.payment import PaymentCreateRequest


async def create_payment(
    db: AsyncSession,
    request: PaymentCreateRequest,
    idempotency_key: str,
) -> Payment:
    # Idempotency check
    existing = await db.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing_payment = existing.scalar_one_or_none()
    if existing_payment:
        return existing_payment

    payment = Payment(
        id=uuid.uuid4(),
        amount=request.amount,
        currency=request.currency,
        description=request.description,
        metadata_=request.metadata,
        status="pending",
        idempotency_key=idempotency_key,
        webhook_url=str(request.webhook_url) if request.webhook_url else None,
    )
    db.add(payment)

    # Outbox event
    outbox_event = OutboxEvent(
        aggregate_id=payment.id,
        event_type="payment.created",
        payload={
            "payment_id": str(payment.id),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "description": payment.description,
            "metadata": payment.metadata_,
            "webhook_url": payment.webhook_url,
        },
        published=False,
    )
    db.add(outbox_event)

    await db.commit()
    await db.refresh(payment)
    return payment


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment
