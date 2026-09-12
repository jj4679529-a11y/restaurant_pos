from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DeliveryWorker
from app.schemas.operations import DeliveryWorkerCreate, DeliveryWorkerUpdate
from app.services.errors import conflict, not_found


def list_workers(session: Session, include_inactive: bool, limit: int, offset: int) -> Sequence[DeliveryWorker]:
    query = select(DeliveryWorker).order_by(DeliveryWorker.id).limit(limit).offset(offset)
    if not include_inactive:
        query = query.where(DeliveryWorker.is_active.is_(True))
    return session.scalars(query).all()


def get_worker(session: Session, worker_id: int) -> DeliveryWorker:
    worker = session.get(DeliveryWorker, worker_id)
    if worker is None:
        raise not_found("Delivery worker")
    return worker


def _commit(session: Session, worker: DeliveryWorker) -> DeliveryWorker:
    try:
        session.add(worker)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("A delivery worker with those values already exists") from exc
    session.refresh(worker)
    return worker


def create_worker(session: Session, data: DeliveryWorkerCreate) -> DeliveryWorker:
    return _commit(session, DeliveryWorker(**data.model_dump()))


def update_worker(session: Session, worker_id: int, data: DeliveryWorkerUpdate) -> DeliveryWorker:
    worker = get_worker(session, worker_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(worker, field, value)
    return _commit(session, worker)
