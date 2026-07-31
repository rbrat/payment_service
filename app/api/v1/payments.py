import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import verify_api_key
from app.core.db import get_db
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentDetailResponse,
    PaymentStatusEnum,
)
from app.services.payment import (
    create_payment,
    get_payment_by_id,
    get_payment_by_idempotency_key,
)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
)
async def create_payment_endpoint(
    body: PaymentCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
):
    existing = await get_payment_by_idempotency_key(session, idempotency_key)
    if existing:
        return PaymentCreateResponse(
            payment_id=existing.id,
            status=PaymentStatusEnum(existing.status),
            created_at=existing.created_at,
        )

    payment = await create_payment(
        session=session,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        metadata=body.metadata,
        webhook_url=body.webhook_url,
        idempotency_key=idempotency_key,
    )
    return PaymentCreateResponse(
        payment_id=payment.id,
        status=PaymentStatusEnum(payment.status),
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    payment = await get_payment_by_id(session, str(payment_id))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentDetailResponse(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.payment_metadata,
        status=PaymentStatusEnum(payment.status),
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
        error_message=payment.error_message,
    )
