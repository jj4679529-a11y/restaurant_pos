from fastapi import APIRouter

from app.api.deps import CashierOrAdminUser, DbSession
from app.schemas.payments import PaymentResponse
from app.services import payment_service

router = APIRouter(tags=["payments"])


@router.post("/orders/{order_id}/pay", response_model=PaymentResponse, description="Confirm an order payment; physical printing and Telegram delivery are asynchronous future concerns.")
def pay_order(order_id: int, db: DbSession, current_user: CashierOrAdminUser):
    try:
        result = payment_service.pay_order(db, order_id, current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "order_id": result.order.id,
        "order_number": result.order.order_number,
        "payment_status": result.order.payment_status,
        "amount": result.payment.amount,
        "paid_at": result.payment.paid_at,
        "payment_id": result.payment.id,
    }
