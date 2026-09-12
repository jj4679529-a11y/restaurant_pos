from fastapi import APIRouter
from app.api.admin_config import router as admin_config_router
from app.api.manual_price_presets import router as presets_router
from app.api.product_images import router as images_router

from app.api.addons import addons_router, router as product_addons_router
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.cancellation import router as cancellation_router
from app.api.delivery_workers import router as delivery_workers_router
from app.api.price_options import router as price_options_router
from app.api.products import router as products_router
from app.api.orders import router as orders_router
from app.api.payments import router as payments_router
from app.api.printing import router as printing_router
from app.api.settings import router as settings_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api")
api_router.include_router(admin_config_router)
api_router.include_router(presets_router)
api_router.include_router(images_router)
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(cancellation_router)
api_router.include_router(products_router)
api_router.include_router(price_options_router)
api_router.include_router(addons_router)
api_router.include_router(product_addons_router)
api_router.include_router(delivery_workers_router)
api_router.include_router(settings_router)
api_router.include_router(orders_router)
api_router.include_router(payments_router)
api_router.include_router(printing_router)
api_router.include_router(users_router)
