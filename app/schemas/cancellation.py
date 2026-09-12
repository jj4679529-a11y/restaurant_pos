from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentStatus
from app.schemas.orders import CancellationActorResponse


class OrderCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OrderCancellationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    order_number: str
    payment_status: PaymentStatus
    cancelled_at: datetime
    cancelled_by: CancellationActorResponse
    cancel_reason: str
