from datetime import date

from fastapi import APIRouter, status

from app.api.deps import CashierOrAdminUser, DbSession, Limit, Offset
from app.models.enums import OrderType, PaymentStatus
from app.schemas.orders import OrderCreate, OrderResponse
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _response(order):
    return {
        "business_date": order.business_day.business_date,
        "cancelled_by": order.canceller,
        **{field: getattr(order, field) for field in (
            "id", "order_number", "order_type", "delivery_worker", "payment_status", "created_at", "paid_at",
            "cancelled_at", "cancel_reason", "total_amount", "items",
        )},
    }


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, description="Create an unpaid order and calculate all prices server-side.")
def create_order(data: OrderCreate, db: DbSession, current_user: CashierOrAdminUser):
    return _response(order_service.create_order(db, data, current_user.id))


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: DbSession, _user: CashierOrAdminUser):
    return _response(order_service.get_order(db, order_id))


@router.get("", response_model=list[OrderResponse])
def list_orders(
    db: DbSession,
    _user: CashierOrAdminUser,
    limit: Limit = 50,
    offset: Offset = 0,
    business_date: date | None = None,
    payment_status: PaymentStatus | None = None,
    order_type: OrderType | None = None,
    delivery_worker_id: int | None = None,
):
    return [_response(order) for order in order_service.list_orders(
        db, business_date, payment_status, order_type, delivery_worker_id, limit, offset
    )]
