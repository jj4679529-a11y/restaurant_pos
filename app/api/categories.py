from fastapi import APIRouter, status

from app.api.deps import AdminUser, CashierOrAdminUser, DbSession, Limit, Offset
from app.schemas.catalog import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import catalog_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse], description="List categories by display order.")
def list_categories(db: DbSession, _user: CashierOrAdminUser, limit: Limit = 50, offset: Offset = 0, include_inactive: bool = False):
    return catalog_service.list_categories(db, include_inactive, limit, offset)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: DbSession, _user: CashierOrAdminUser):
    return catalog_service.get_category(db, category_id)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: DbSession, _admin: AdminUser):
    return catalog_service.create_category(db, data)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, data: CategoryUpdate, db: DbSession, _admin: AdminUser):
    return catalog_service.update_category(db, category_id, data)
