from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import UnitType

PRICE_NOT_CONFIGURED = 0

OSH_PORTIONS: tuple[Decimal, ...] = (Decimal("0.5"), Decimal("1"))

CATEGORY_MILLIY = "Milliy taomlar"
CATEGORY_SALADS = "Salatlar"
CATEGORY_BREAD = "Non"
CATEGORY_TEA = "Choy va Novot"
CATEGORY_DRINKS = "Ichimliklar"


@dataclass(frozen=True)
class CategorySpec:
    name: str
    sort_order: int


@dataclass(frozen=True)
class PriceOptionSpec:
    price: int
    quantity: Decimal = Decimal("1.000")
    source: str = "configurable"


@dataclass(frozen=True)
class ProductSpec:
    name: str
    category_name: str
    unit_type: UnitType
    base_price: int = PRICE_NOT_CONFIGURED
    allows_manual_price: bool = False
    price_options: tuple[PriceOptionSpec, ...] = ()


@dataclass(frozen=True)
class AddOnSpec:
    name: str
    unit_type: UnitType
    allows_manual_price: bool = False
    base_price: int = PRICE_NOT_CONFIGURED


@dataclass(frozen=True)
class DeliveryWorkerSpec:
    name: str
    phone: str


@dataclass(frozen=True)
class SettingSpec:
    key: str
    value: str


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(CATEGORY_MILLIY, 1),
    CategorySpec(CATEGORY_SALADS, 2),
    CategorySpec(CATEGORY_BREAD, 3),
    CategorySpec(CATEGORY_TEA, 4),
    CategorySpec(CATEGORY_DRINKS, 5),
)

PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec("Osh", CATEGORY_MILLIY, UnitType.PORTION),
    ProductSpec("Sho'rva", CATEGORY_MILLIY, UnitType.PORTION),
    ProductSpec("Jizz", CATEGORY_MILLIY, UnitType.AMOUNT, allows_manual_price=True),
    ProductSpec("Mastava", CATEGORY_MILLIY, UnitType.PORTION),
    ProductSpec("Manti", CATEGORY_MILLIY, UnitType.PIECE),
    ProductSpec("Non 1", CATEGORY_BREAD, UnitType.PIECE),
    ProductSpec("Non 2", CATEGORY_BREAD, UnitType.PIECE),
    ProductSpec("Choy", CATEGORY_TEA, UnitType.PIECE),
    ProductSpec("Novot", CATEGORY_TEA, UnitType.PIECE),
    ProductSpec("Kompot", CATEGORY_DRINKS, UnitType.LITER),
    ProductSpec("Ayran", CATEGORY_DRINKS, UnitType.LITER),
    ProductSpec("Sovuq ichimliklar", CATEGORY_DRINKS, UnitType.LITER),
)

OSH_ADDONS: tuple[AddOnSpec, ...] = (
    AddOnSpec("Tuxum 1", UnitType.PIECE),
    AddOnSpec("Tuxum 2", UnitType.PIECE),
    AddOnSpec("Qazi", UnitType.PIECE),
    AddOnSpec(
        "Go'sht",
        UnitType.AMOUNT,
        allows_manual_price=True,
    ),
)

DEMO_DELIVERY_WORKERS: tuple[DeliveryWorkerSpec, ...] = (
    DeliveryWorkerSpec("Ali", "demo-ali"),
    DeliveryWorkerSpec("Vali", "demo-vali"),
    DeliveryWorkerSpec("Hasan", "demo-hasan"),
)

SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("restaurant_name", "Restaurant POS"),
    SettingSpec("business_day_start", "06:00"),
    SettingSpec("timezone", "Asia/Tashkent"),
)
