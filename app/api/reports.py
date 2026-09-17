"""Owner-facing daily report, using stored order/payment snapshots."""
from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter
from sqlalchemy import func, select
from app.api.deps import AdminUser, DbSession
from app.models import BusinessDay, Category, Product, Order, OrderItem, Payment, PaymentStatus, User, DeliveryWorker, OrderType
from app.services.business_day_service import get_current_business_date

router = APIRouter(prefix='/admin/reports', tags=['reports'])


@router.get('/daily')
def daily_report(db: DbSession, _admin: AdminUser, business_date: date | None = None,
                 period: Literal['kunlik', 'haftalik', 'oylik'] = 'kunlik', order_type: OrderType | None = None):
    day_date = business_date or get_current_business_date(session=db)
    start = day_date
    if period == 'haftalik':
        start = day_date - timedelta(days=day_date.weekday())
    elif period == 'oylik':
        start = day_date.replace(day=1)
    day_ids = select(BusinessDay.id).where(BusinessDay.business_date >= start, BusinessDay.business_date <= day_date)
    scope = Order.business_day_id.in_(day_ids)
    paid = Order.payment_status == PaymentStatus.PAID
    type_scope = (Order.order_type == order_type) if order_type else True
    count, total = db.execute(select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(scope, paid, type_scope)).one()
    all_count = db.scalar(select(func.count(Order.id)).where(scope, type_scope))
    def amounts(query):
        return [{'id': row[0], 'name': row[1], 'order_count': int(row[2]), 'amount': int(row[3])} for row in db.execute(query)]
    cashiers = amounts(select(User.id, User.name, func.count(Payment.id), func.sum(Payment.amount))
        .join(Payment, Payment.created_by == User.id).join(Order, Order.id == Payment.order_id)
        .where(scope, paid, type_scope, Payment.status == PaymentStatus.PAID).group_by(User.id, User.name).order_by(User.name))
    workers = amounts(select(DeliveryWorker.id, DeliveryWorker.name, func.count(Order.id), func.sum(Order.total_amount))
        .join(Order, Order.delivery_worker_id == DeliveryWorker.id).where(scope, paid, type_scope)
        .group_by(DeliveryWorker.id, DeliveryWorker.name).order_by(DeliveryWorker.name))
    products = []
    for row in db.execute(select(Product.id, Product.name, func.count(func.distinct(Order.id)),
                                  func.sum(OrderItem.total_price), func.sum(OrderItem.quantity))
            .join(OrderItem, OrderItem.product_id == Product.id).join(Order, Order.id == OrderItem.order_id)
            .where(scope, paid, type_scope).group_by(Product.id, Product.name).order_by(Product.name)):
        products.append({'id': row[0], 'name': row[1], 'order_count': row[2], 'amount': int(row[3]), 'quantity': str(row[4])})
    categories = amounts(select(Category.id, Category.name, func.count(func.distinct(Order.id)), func.sum(OrderItem.total_price))
        .join(Product, Product.category_id == Category.id).join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id).where(scope, paid, type_scope)
        .group_by(Category.id, Category.name).order_by(Category.name))
    by_type = {kind.value: int(db.scalar(select(func.coalesce(func.sum(Order.total_amount), 0)).where(scope, paid, type_scope, Order.order_type == kind)))
               for kind in (OrderType.CHAYKHANA, OrderType.DELIVERY)}
    return {'business_date': day_date, 'total_order_count': all_count, 'paid_order_count': count,
            'total_paid_amount': int(total), 'categories': categories, 'products': products,
            'cashiers': cashiers, 'delivery_workers': workers, 'by_order_type': by_type}
