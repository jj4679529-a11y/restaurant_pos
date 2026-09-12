from sqlalchemy.orm import Session

from app.seed.config import SeedResult, SeedSettings
from app.seed.menu import seed_categories, seed_osh_addons, seed_products, seed_final_pricing
from app.seed.settings import seed_settings
from app.seed.users import seed_admin
from app.seed.workers import seed_delivery_workers


def seed_all(session: Session, settings: SeedSettings) -> SeedResult:
    result = SeedResult(admin_created=False)
    seed_admin(
        session,
        username=settings.ADMIN_USERNAME,
        password=settings.ADMIN_PASSWORD,
        name=settings.ADMIN_NAME,
        result=result,
    )
    categories = seed_categories(session, result)
    products = seed_products(session, categories, result)
    seed_osh_addons(session, products["Osh"], result)
    seed_final_pricing(session, products, settings, result)
    seed_delivery_workers(session, result)
    seed_settings(session, result)
    return result
