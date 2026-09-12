from fastapi import APIRouter, status

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.schemas.catalog import PriceOptionCreate, PriceOptionResponse, PriceOptionUpdate
from app.services import catalog_service

router = APIRouter(tags=["price options"])


@router.get("/products/{product_id}/price-options", response_model=list[PriceOptionResponse])
def list_price_options(product_id: int, db: DbSession, _user: CashierOrAdminUser, limit: Limit = 50, offset: Offset = 0):
    return catalog_service.list_price_options(db, product_id, limit, offset)


@router.post("/products/{product_id}/price-options", response_model=PriceOptionResponse, status_code=status.HTTP_201_CREATED)
def create_price_option(product_id: int, data: PriceOptionCreate, db: DbSession, _admin: AdminUser):
    return catalog_service.create_price_option(db, product_id, data)


@router.patch("/price-options/{price_option_id}", response_model=PriceOptionResponse)
def update_price_option(price_option_id: int, data: PriceOptionUpdate, db: DbSession, _admin: AdminUser):
    return catalog_service.update_price_option(db, price_option_id, data)
