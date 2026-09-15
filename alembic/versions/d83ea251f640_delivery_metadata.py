"""Cashier phone and packaged-drink volume; no existing data rewritten."""
from alembic import op
import sqlalchemy as sa

revision = 'd83ea251f640'
down_revision = 'c72d9a104e53'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(32), nullable=True))
    op.add_column('products', sa.Column('volume_liters', sa.Numeric(8, 3), nullable=True))


def downgrade():
    raise RuntimeError('Forward-only delivery migration: preserve phone and volume data.')
