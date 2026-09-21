"""add addon image path

Revision ID: 3f1268a26b2a
Revises: 6acae65eaa75
Create Date: 2026-09-21 03:43:30.989210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f1268a26b2a'
down_revision: Union[str, Sequence[str], None] = '6acae65eaa75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "add_ons",
        sa.Column(
            "image_path",
            sa.String(length=512),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("add_ons", "image_path")
