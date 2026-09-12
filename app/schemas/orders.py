from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderType, PaymentStatus


class OrderItemAddOnCreate(BaseModel):
    addon_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    manual_price: int | None = Field(default=None, gt=0)
    selected_price_option_id: int | None = Field(default=None, gt=0)


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    selected_price_option_id: int | None = Field(default=None, gt=0)
    manual_price: int | None = Field(default=None, gt=0)
    addons: list[OrderItemAddOnCreate] = Field(default_factory=list)


class OrderCreate(BaseModel):
    order_type: OrderType
    delivery_worker_id: int | None = Field(default=None, gt=0)
    items: list[OrderItemCreate] = Field(min_length=1)


class ProductSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AddOnSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class OrderItemAddOnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    addon: AddOnSnapshotResponse
    quantity: Decimal
    unit_price: int
    total_price: int
    manual_price: int | None
    # The database column predates the API naming convention.  Keep the API
    # field consistent with OrderItem while reading the nullable ORM attribute.
    selected_price_option_id: int | None = Field(default=None, validation_alias="price_option_id")


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductSnapshotResponse
    quantity: Decimal
    unit_price: int
    total_price: int
    selected_price_option_id: int | None
    manual_price: int | None
    addons: list[OrderItemAddOnResponse]


class DeliveryWorkerSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CancellationActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    business_date: date
    order_type: OrderType
    delivery_worker: DeliveryWorkerSnapshotResponse | None
    payment_status: PaymentStatus
    created_at: datetime
    paid_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: CancellationActorResponse | None
    cancel_reason: str | None
    total_amount: int
    items: list[OrderItemResponse]
