from fastapi import APIRouter, status

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.schemas.catalog import ProductCreate, ProductResponse, ProductUpdate
from app.services import catalog_service

router = APIRouter(prefix="/products", tags=["products"])


def _response(product):
    return {
        **{field: getattr(product, field) for field in ("id", "category_id", "name", "unit_type", "base_price", "allows_manual_price", "is_active")},
        "image_path": product.image_path,
        "manual_price_presets": [preset for preset in product.manual_price_presets if preset.is_active],
        "price_options": product.price_options,
        "available_addons": [
            {**{field: getattr(link.addon, field) for field in ("id", "name", "unit_type", "base_price", "allows_manual_price", "is_active")}, "is_required": link.is_required, "relationship_active": link.is_active, "manual_price_presets": [preset for preset in link.addon.manual_price_presets if preset.is_active]}
            for link in product.product_addons if link.is_active and link.addon.is_active
        ],
    }


@router.get("", response_model=list[ProductResponse], description="List active products, with their options and active add-ons.")
def list_products(db: DbSession, _user: CashierOrAdminUser, limit: Limit = 50, offset: Offset = 0, category_id: int | None = None, is_active: bool | None = None, search: str | None = None):
    return [_response(product) for product in catalog_service.list_products(db, category_id, is_active, search, limit, offset)]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: DbSession, _user: CashierOrAdminUser):
    return _response(catalog_service.get_product(db, product_id))


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: DbSession, _admin: AdminUser):
    return _response(catalog_service.create_product(db, data))


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, data: ProductUpdate, db: DbSession, _admin: AdminUser):
    return _response(catalog_service.update_product(db, product_id, data))
