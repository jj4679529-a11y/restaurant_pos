from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.models import AddOn, ManualPricePreset, Product
from app.schemas.catalog import ManualPricePresetCreate, ManualPricePresetResponse, ManualPricePresetUpdate
from app.services.errors import ServiceError, conflict, not_found

router = APIRouter(prefix="/manual-price-presets", tags=["manual price presets"])


@router.get("", response_model=list[ManualPricePresetResponse])
def list_presets(db: DbSession, _user: CashierOrAdminUser, product_id: int | None = None, addon_id: int | None = None, limit: Limit = 50, offset: Offset = 0):
    query = select(ManualPricePreset).where(ManualPricePreset.is_active.is_(True))
    if product_id is not None:
        query = query.where(ManualPricePreset.product_id == product_id)
    if addon_id is not None:
        query = query.where(ManualPricePreset.addon_id == addon_id)
    return db.scalars(query.order_by(ManualPricePreset.sort_order, ManualPricePreset.id).limit(limit).offset(offset)).all()


@router.post("", response_model=ManualPricePresetResponse, status_code=201)
def create_preset(data: ManualPricePresetCreate, db: DbSession, _admin: AdminUser):
    target = db.get(Product, data.product_id) if data.product_id else db.get(AddOn, data.addon_id)
    if target is None:
        raise not_found("Preset target")
    if not target.allows_manual_price:
        raise ServiceError(400, "manual_price_not_allowed", "Target must allow manual prices")
    preset = ManualPricePreset(**data.model_dump())
    return _save(db, preset)


@router.patch("/{preset_id}", response_model=ManualPricePresetResponse)
def update_preset(preset_id: int, data: ManualPricePresetUpdate, db: DbSession, _admin: AdminUser):
    preset = db.get(ManualPricePreset, preset_id)
    if preset is None:
        raise not_found("Manual price preset")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(preset, key, value)
    return _save(db, preset)


def _save(db, preset):
    try:
        db.add(preset)
        db.commit()
        db.refresh(preset)
    except IntegrityError as error:
        db.rollback()
        raise conflict("A preset with this amount already exists for the target") from error
    return preset
