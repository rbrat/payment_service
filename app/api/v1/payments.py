import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.base import get_db
from app.schemas.payment import PaymentCreateRequest, PaymentCreateResponse, PaymentDetailResponse
from app.services.payment_service import create_payment, get_payment

router = APIRouter(prefix="/payments",
                   tags=["payments"], dependencies=[Depends(verify_api_key)])


@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentCreateResponse,
)
async def create_payment_endpoint(
    request: PaymentCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
) -> PaymentCreateResponse:
    payment = await create_payment(db, request, idempotency_key)
    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailResponse,
)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PaymentDetailResponse:
    payment = await get_payment(db, payment_id)
    return payment
