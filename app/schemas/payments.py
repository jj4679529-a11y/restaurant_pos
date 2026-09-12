from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    order_number: str
    payment_status: PaymentStatus
    amount: int
    paid_at: datetime
    payment_id: int
