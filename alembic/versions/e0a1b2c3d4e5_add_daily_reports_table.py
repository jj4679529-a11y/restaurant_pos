"""add daily_reports table

Revision ID: e0a1b2c3d4e5
Revises: d83ea251f640
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e0a1b2c3d4e5'
down_revision = 'd83ea251f640'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'daily_reports',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('business_day_id', sa.Integer(), nullable=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('snapshot', sa.Text(), nullable=True),
        sa.Column('printer_id', sa.Integer(), nullable=True),
        sa.Column('total_paid_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('paid_order_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cancelled_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chaykhana_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivery_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['business_day_id'], ['business_days.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['printer_id'], ['printers.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('business_date', name='uq_daily_reports_business_date'),
    )
    op.create_index(op.f('ix_daily_reports_business_date'), 'daily_reports', ['business_date'], unique=False)


def downgrade():
    op.drop_table('daily_reports')
