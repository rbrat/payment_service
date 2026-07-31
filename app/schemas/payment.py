import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CurrencyEnum(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatusEnum(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: CurrencyEnum
    description: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str = Field(min_length=1, max_length=2000)


class PaymentCreateResponse(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatusEnum
    created_at: datetime


class PaymentDetailResponse(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal
    currency: CurrencyEnum
    description: str
    metadata: dict[str, Any]
    status: PaymentStatusEnum
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class WebhookPayload(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatusEnum
    error_message: str | None = None
