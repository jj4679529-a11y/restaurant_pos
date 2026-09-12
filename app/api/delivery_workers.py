from fastapi import APIRouter, status

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.models import UserRole
from app.services.errors import ServiceError
from app.schemas.operations import DeliveryWorkerCreate, DeliveryWorkerResponse, DeliveryWorkerUpdate
from app.services import worker_service

router = APIRouter(prefix="/delivery-workers", tags=["delivery workers"])


@router.get("", response_model=list[DeliveryWorkerResponse])
def list_delivery_workers(db: DbSession, user: CashierOrAdminUser, limit: Limit = 50, offset: Offset = 0, include_inactive: bool = False):
    if include_inactive and user.role is not UserRole.ADMIN:
        raise ServiceError(403, "FORBIDDEN", "Cashiers can only view active delivery workers")
    return worker_service.list_workers(db, include_inactive, limit, offset)


@router.get("/{worker_id}", response_model=DeliveryWorkerResponse)
def get_delivery_worker(worker_id: int, db: DbSession, user: CashierOrAdminUser):
    worker = worker_service.get_worker(db, worker_id)
    if not worker.is_active and user.role is not UserRole.ADMIN:
        raise ServiceError(403, "FORBIDDEN", "Cashiers can only view active delivery workers")
    return worker


@router.post("", response_model=DeliveryWorkerResponse, status_code=status.HTTP_201_CREATED)
def create_delivery_worker(data: DeliveryWorkerCreate, db: DbSession, _admin: AdminUser):
    return worker_service.create_worker(db, data)


@router.patch("/{worker_id}", response_model=DeliveryWorkerResponse)
def update_delivery_worker(worker_id: int, data: DeliveryWorkerUpdate, db: DbSession, _admin: AdminUser):
    return worker_service.update_worker(db, worker_id, data)
