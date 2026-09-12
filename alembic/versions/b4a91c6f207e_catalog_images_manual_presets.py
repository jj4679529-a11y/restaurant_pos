"""Optional local product images and reusable manual-price presets.

Revision ID: b4a91c6f207e
Revises: 733f8f399dc3
"""
from alembic import op
import sqlalchemy as sa

revision = "b4a91c6f207e"
down_revision = "733f8f399dc3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("image_path", sa.String(512), nullable=True))
    op.create_table(
        "manual_price_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT")),
        sa.Column("addon_id", sa.Integer(), sa.ForeignKey("add_ons.id", ondelete="RESTRICT")),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("(product_id IS NOT NULL AND addon_id IS NULL) OR (product_id IS NULL AND addon_id IS NOT NULL)", name="ck_manual_preset_one_target"),
        sa.CheckConstraint("amount > 0", name="ck_manual_preset_positive_amount"),
        sa.UniqueConstraint("product_id", "amount", name="uq_manual_preset_product_amount"),
        sa.UniqueConstraint("addon_id", "amount", name="uq_manual_preset_addon_amount"),
    )


def downgrade():
    op.drop_table("manual_price_presets")
    op.drop_column("products", "image_path")
