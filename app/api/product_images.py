from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import CashierOrAdminUser
from app.core.config import get_settings
from app.services.errors import not_found

router = APIRouter(tags=["product images"])


def resolve_product_image(root: Path, reference: str) -> Path:
    root = root.resolve()
    candidate = (root / reference).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or not candidate.is_file():
        raise not_found("Product image")
    return candidate


@router.get("/product-images/{reference:path}")
def get_image(reference: str, _user: CashierOrAdminUser):
    return FileResponse(resolve_product_image(get_settings().PRODUCT_MEDIA_DIR, reference))
