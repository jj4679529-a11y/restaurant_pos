from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pathlib import PurePosixPath

from app.models.enums import UnitType


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ManualPricePresetResponse(Schema):
    id: int
    product_id: int | None
    addon_id: int | None
    amount: int
    sort_order: int
    is_active: bool


class ManualPricePresetCreate(Schema):
    product_id: int | None = Field(default=None, gt=0)
    addon_id: int | None = Field(default=None, gt=0)
    amount: int = Field(gt=0, le=2_147_483_647)
    sort_order: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.product_id is None) == (self.addon_id is None):
            raise ValueError("Exactly one product or addon target is required")
        return self


class ManualPricePresetUpdate(Schema):
    amount: int | None = Field(default=None, gt=0, le=2_147_483_647)
    sort_order: int | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def no_explicit_null(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Preset fields cannot be null")
        return self


class ImageReference(Schema):
    image_path: str | None = Field(default=None, max_length=512)

    @field_validator("image_path")
    @classmethod
    def local_image_reference(cls, value):
        if value is None:
            return value
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts or any(c in value for c in ("\\", ":", "?", "#")):
            raise ValueError("Image must be a relative local media path")
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Supported images: PNG, JPEG, WebP")
        return value


class CategoryCreate(Schema):
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(Schema):
    id: int
    name: str
    sort_order: int
    is_active: bool


class PriceOptionCreate(Schema):
    name: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    price: int = Field(gt=0)
    is_active: bool = True


class PriceOptionUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: Decimal | None = Field(default=None, gt=0, decimal_places=3)
    price: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class PriceOptionResponse(Schema):
    id: int
    product_id: int
    name: str
    quantity: Decimal
    price: int
    is_active: bool


class AddOnCreate(Schema):
    name: str = Field(min_length=1, max_length=255)
    unit_type: UnitType
    base_price: int = Field(ge=0)
    allows_manual_price: bool = False
    is_active: bool = True


class AddOnUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit_type: UnitType | None = None
    base_price: int | None = Field(default=None, ge=0)
    allows_manual_price: bool | None = None
    is_active: bool | None = None


class AddOnResponse(Schema):
    id: int
    name: str
    unit_type: UnitType
    base_price: int
    allows_manual_price: bool
    is_active: bool
    manual_price_presets: list[ManualPricePresetResponse] = Field(default_factory=list)


class AvailableAddOnResponse(AddOnResponse):
    is_required: bool
    relationship_active: bool


class ProductCreate(ImageReference):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    unit_type: UnitType
    base_price: int = Field(ge=0)
    allows_manual_price: bool = False
    is_active: bool = True


class ProductUpdate(ImageReference):
    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit_type: UnitType | None = None
    base_price: int | None = Field(default=None, ge=0)
    allows_manual_price: bool | None = None
    is_active: bool | None = None


class ProductResponse(Schema):
    id: int
    category_id: int
    name: str
    unit_type: UnitType
    base_price: int
    allows_manual_price: bool
    is_active: bool
    price_options: list[PriceOptionResponse]
    available_addons: list[AvailableAddOnResponse]
    image_path: str | None = None
    manual_price_presets: list[ManualPricePresetResponse] = Field(default_factory=list)


class ProductAddOnResponse(Schema):
    product_id: int
    addon_id: int
    is_required: bool
    is_active: bool
