from fastapi import APIRouter, status

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.schemas.catalog import AddOnCreate, AddOnResponse, AddOnUpdate, ProductAddOnResponse
from app.services import catalog_service

router = APIRouter(tags=["add-ons"])
addons_router = APIRouter(prefix="/addons", tags=["add-ons"])


@addons_router.get("", response_model=list[AddOnResponse])
def list_addons(db: DbSession, _user: CashierOrAdminUser, limit: Limit = 50, offset: Offset = 0, include_inactive: bool = False):
    return catalog_service.list_addons(db, include_inactive, limit, offset)


@addons_router.get("/{addon_id}", response_model=AddOnResponse)
def get_addon(addon_id: int, db: DbSession, _user: CashierOrAdminUser):
    return catalog_service.get_addon(db, addon_id)


@addons_router.post("", response_model=AddOnResponse, status_code=status.HTTP_201_CREATED)
def create_addon(data: AddOnCreate, db: DbSession, _admin: AdminUser):
    return catalog_service.create_addon(db, data)


@addons_router.patch("/{addon_id}", response_model=AddOnResponse)
def update_addon(addon_id: int, data: AddOnUpdate, db: DbSession, _admin: AdminUser):
    return catalog_service.update_addon(db, addon_id, data)


@router.post("/products/{product_id}/addons/{addon_id}", response_model=ProductAddOnResponse, status_code=status.HTTP_201_CREATED)
def link_addon(product_id: int, addon_id: int, db: DbSession, _admin: AdminUser):
    return catalog_service.link_addon(db, product_id, addon_id)
