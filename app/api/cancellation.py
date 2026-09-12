from fastapi import APIRouter

from app.api.deps import CashierOrAdminUser, DbSession
from app.schemas.cancellation import OrderCancellationResponse, OrderCancelRequest
from app.services import cancellation_service

router = APIRouter(tags=["orders"])


@router.post("/orders/{order_id}/cancel", response_model=OrderCancellationResponse)
def cancel_order(order_id: int, data: OrderCancelRequest, db: DbSession, current_user: CashierOrAdminUser):
    try:
        result = cancellation_service.cancel_order(db, order_id, data.reason, current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "order_id": result.order.id,
        "order_number": result.order.order_number,
        "payment_status": result.order.payment_status,
        "cancelled_at": result.order.cancelled_at,
        "cancelled_by": result.order.canceller,
        "cancel_reason": result.order.cancel_reason,
    }
