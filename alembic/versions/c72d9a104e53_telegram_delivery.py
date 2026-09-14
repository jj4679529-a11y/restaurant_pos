"""Durable Telegram retry scheduling and event deduplication.

Revision ID: c72d9a104e53
Revises: b4a91c6f207e
"""
from alembic import op
import sqlalchemy as sa

revision = "c72d9a104e53"
down_revision = "b4a91c6f207e"
branch_labels = None
depends_on = None


def upgrade():
    # Commit enum additions before any transaction can use their new labels.
    with op.get_context().autocommit_block():
        for value in ("PRINTER_FAILURE", "DELIVERY_ASSIGNED", "BOT_REPLY"):
            op.execute(f"ALTER TYPE telegram_message_type ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("telegram_outbox", sa.Column("event_key", sa.String(160), nullable=True))
    op.add_column("telegram_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_telegram_outbox_event_key", "telegram_outbox", ["event_key"])
    op.create_index("ix_telegram_outbox_next_attempt_at", "telegram_outbox", ["next_attempt_at"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM telegram_outbox WHERE message_type::text IN ('PRINTER_FAILURE','DELIVERY_ASSIGNED','BOT_REPLY'))")):
        raise RuntimeError("Downgrade refused: new Telegram event history must be preserved.")
    op.drop_index("ix_telegram_outbox_next_attempt_at", table_name="telegram_outbox")
    op.drop_constraint("uq_telegram_outbox_event_key", "telegram_outbox", type_="unique")
    op.drop_column("telegram_outbox", "next_attempt_at")
    op.drop_column("telegram_outbox", "event_key")
    # PostgreSQL enum labels are retained; removing them requires type recreation.
