from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeliveryWorker
from app.seed.catalog import DEMO_DELIVERY_WORKERS
from app.seed.config import SeedResult


def seed_delivery_workers(session: Session, result: SeedResult) -> None:
    for spec in DEMO_DELIVERY_WORKERS:
        worker = session.scalars(
            select(DeliveryWorker).where(DeliveryWorker.name == spec.name)
        ).one_or_none()
        if worker is not None:
            continue
        session.add(
            DeliveryWorker(
                name=spec.name,
                phone=spec.phone,
                is_active=True,
            )
        )
        result.delivery_workers_created += 1
