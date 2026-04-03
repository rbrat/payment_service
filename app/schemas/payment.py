import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Literal

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: Literal["RUB", "USD", "EUR"]
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[dict[str, Any]] = None
    webhook_url: Optional[str] = Field(None)


class PaymentCreateResponse(BaseModel):
    payment_id: uuid.UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentDetailResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: str
    description: Optional[str]
    metadata: Optional[dict[str, Any]] = Field(alias="metadata_")
    status: str
    idempotency_key: str
    webhook_url: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True, "populate_by_name": True}
