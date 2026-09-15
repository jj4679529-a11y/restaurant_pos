from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.enums import UnitType
from app.models.mixins import CreatedAtMixin, TimestampMixin
from app.models.types import pg_enum


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    volume_liters: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    unit_type: Mapped[UnitType] = mapped_column(pg_enum(UnitType, "unit_type"), nullable=False)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)
    allows_manual_price: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    category: Mapped[Category] = relationship(back_populates="products")
    price_options: Mapped[list["PriceOption"]] = relationship(back_populates="product")
    product_addons: Mapped[list["ProductAddOn"]] = relationship(back_populates="product")
    manual_price_presets: Mapped[list["ManualPricePreset"]] = relationship(back_populates="product", order_by="ManualPricePreset.sort_order, ManualPricePreset.id")


class PriceOption(CreatedAtMixin, Base):
    __tablename__ = "price_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    product: Mapped[Product] = relationship(back_populates="price_options")


class AddOn(TimestampMixin, Base):
    __tablename__ = "add_ons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(pg_enum(UnitType, "unit_type"), nullable=False)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)
    allows_manual_price: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    product_addons: Mapped[list["ProductAddOn"]] = relationship(back_populates="addon")
    manual_price_presets: Mapped[list["ManualPricePreset"]] = relationship(back_populates="addon", order_by="ManualPricePreset.sort_order, ManualPricePreset.id")


class ManualPricePreset(Base):
    __tablename__ = "manual_price_presets"
    __table_args__ = (
        CheckConstraint("(product_id IS NOT NULL AND addon_id IS NULL) OR (product_id IS NULL AND addon_id IS NOT NULL)", name="ck_manual_preset_one_target"),
        CheckConstraint("amount > 0", name="ck_manual_preset_positive_amount"),
        UniqueConstraint("product_id", "amount", name="uq_manual_preset_product_amount"),
        UniqueConstraint("addon_id", "amount", name="uq_manual_preset_addon_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("add_ons.id", ondelete="RESTRICT"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    product: Mapped["Product | None"] = relationship(back_populates="manual_price_presets")
    addon: Mapped["AddOn | None"] = relationship(back_populates="manual_price_presets")


class ProductAddOn(Base):
    __tablename__ = "product_addons"
    __table_args__ = (
        UniqueConstraint("product_id", "addon_id", name="uq_product_addons_product_addon"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    addon_id: Mapped[int] = mapped_column(ForeignKey("add_ons.id", ondelete="RESTRICT"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    product: Mapped[Product] = relationship(back_populates="product_addons")
    addon: Mapped[AddOn] = relationship(back_populates="product_addons")
