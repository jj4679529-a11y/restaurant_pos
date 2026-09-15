"""Small Admin-only capabilities missing from the existing catalog API."""
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Request
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession, Limit, Offset
from app.core.config import get_settings
from app.models import AddOn, ManualPricePreset, PriceOption, Printer, PrinterConnectionType, Product, ProductAddOn, Setting, UnitType
from app.schemas.catalog import ManualPricePresetResponse, PriceOptionResponse, ProductAddOnResponse
from app.schemas.settings import SettingResponse, SettingUpdate
from app.services.errors import ServiceError, conflict, not_found
from app.menu_rules import menu_key, OSH_ADDONS

router = APIRouter(prefix='/admin', tags=['admin configuration'])
SAFE_SETTINGS = {'restaurant_name', 'business_day_start', 'timezone'}


@router.post('/menu/prepare')
def prepare_menu(db: DbSession, _admin: AdminUser):
    from app.services.final_menu_service import prepare_final_menu
    try:
        result = prepare_final_menu(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


class PrinterData(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    terminal_name: str = Field(min_length=1, max_length=64)
    connection_type: PrinterConnectionType
    address: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class PrinterResponse(PrinterData):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OshPrices(BaseModel):
    half_price: int = Field(gt=0, le=2_147_483_647)
    full_price: int = Field(gt=0, le=2_147_483_647)


class LinkState(BaseModel):
    is_active: bool
    is_required: bool = False


def save(db, record):
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError as error:
        db.rollback()
        raise conflict('Configuration conflicts with existing records') from error
    return record


@router.get('/printers', response_model=list[PrinterResponse])
def printers(db: DbSession, _admin: AdminUser, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(select(Printer).order_by(Printer.id).limit(limit).offset(offset)).all()


@router.post('/printers', response_model=PrinterResponse, status_code=201)
def create_printer(data: PrinterData, db: DbSession, _admin: AdminUser):
    return save(db, Printer(**data.model_dump()))


@router.put('/printers/{printer_id}', response_model=PrinterResponse)
def update_printer(printer_id: int, data: PrinterData, db: DbSession, _admin: AdminUser):
    record = db.get(Printer, printer_id)
    if record is None:
        raise not_found('Printer')
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    return save(db, record)


@router.get('/manual-price-presets', response_model=list[ManualPricePresetResponse])
def all_presets(db: DbSession, _admin: AdminUser, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(select(ManualPricePreset).order_by(ManualPricePreset.sort_order, ManualPricePreset.id).limit(limit).offset(offset)).all()


@router.get('/products/{product_id}/addons', response_model=list[ProductAddOnResponse])
def addon_links(product_id: int, db: DbSession, _admin: AdminUser):
    return db.scalars(select(ProductAddOn).where(ProductAddOn.product_id == product_id)).all()


@router.put('/products/{product_id}/addons/{addon_id}', response_model=ProductAddOnResponse)
def set_link(product_id: int, addon_id: int, data: LinkState, db: DbSession, _admin: AdminUser):
    product, addon = db.get(Product, product_id), db.get(AddOn, addon_id)
    if product is None or addon is None:
        raise not_found('Product or addon')
    if data.is_active and menu_key(addon.name) in OSH_ADDONS and menu_key(product.name) != 'osh':
        raise ServiceError(400, 'osh_addon_only', 'This addon is available only for Osh')
    if data.is_active and (not product.is_active or not addon.is_active):
        raise ServiceError(400, 'inactive_catalog_item', 'Activate product and addon first')
    record = db.scalar(select(ProductAddOn).where(ProductAddOn.product_id == product_id, ProductAddOn.addon_id == addon_id))
    if record is None:
        record = ProductAddOn(product_id=product_id, addon_id=addon_id)
    record.is_active, record.is_required = data.is_active, data.is_required
    return save(db, record)


@router.put('/products/{product_id}/osh-prices', response_model=list[PriceOptionResponse])
def osh_prices(product_id: int, data: OshPrices, db: DbSession, _admin: AdminUser):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise not_found('Product')
    if product.name.strip().casefold() != 'osh':
        raise ServiceError(400, 'NOT_OSH', 'This editor is for Osh only')
    options = db.scalars(select(PriceOption).where(PriceOption.product_id == product_id).with_for_update()).all()
    selected = []
    for quantity, amount in ((Decimal('0.5'), data.half_price), (Decimal('1'), data.full_price)):
        name = f'{quantity} porsiya'
        option = next((o for o in options if o.name == name and o.quantity == quantity), None)
        if option is None:
            option = PriceOption(product_id=product_id, name=name, quantity=quantity)
            db.add(option)
        option.price, option.is_active = amount, True
        selected.append(option)
    for option in options:
        if option not in selected:
            option.is_active = False
    product.allows_manual_price, product.base_price, product.unit_type = False, 0, UnitType.PORTION
    save(db, product)
    return selected


@router.get('/settings', response_model=list[SettingResponse])
def safe_settings(db: DbSession, _admin: AdminUser):
    return db.scalars(select(Setting).where(Setting.key.in_(SAFE_SETTINGS)).order_by(Setting.key)).all()


@router.patch('/settings/{key}', response_model=SettingResponse)
def update_safe_setting(key: str, data: SettingUpdate, db: DbSession, _admin: AdminUser):
    if key not in SAFE_SETTINGS:
        raise ServiceError(403, 'protected_setting', 'Setting is not available in Admin UI')
    from app.services.settings_service import validate_setting
    validate_setting(key, data.value)
    if not data.value.strip():
        raise ServiceError(422, 'EMPTY_VALUE', 'Value must not be blank')
    record = db.scalar(select(Setting).where(Setting.key == key))
    if record is None:
        record = Setting(key=key)
    record.value = data.value.strip()
    return save(db, record)


@router.post('/product-images', status_code=201)
async def upload_image(request: Request, _admin: AdminUser):
    # Do not trust an extension or a client-supplied path. Bound bytes and pixels,
    # decode and re-encode a single frame, stripping metadata and embedded payloads.
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 5 * 1024 * 1024:
            raise ServiceError(413, 'IMAGE_TOO_LARGE', 'Maximum image size is 5 MB')
        body.extend(chunk)
    try:
        with Image.open(BytesIO(body), formats=['PNG', 'JPEG', 'WEBP']) as image:
            if image.width * image.height > 12_000_000:
                raise ValueError('Too many pixels')
            image.load()
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=90)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ServiceError(422, 'INVALID_IMAGE', 'Use a valid PNG/JPEG/WebP image up to 12 megapixels') from error
    root = get_settings().PRODUCT_MEDIA_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    reference = f'{uuid4().hex}.jpg'
    with (root / reference).open('xb') as target:
        target.write(output.getvalue())
    return {'image_path': reference}
