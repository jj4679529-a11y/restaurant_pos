"""add addon image path

Revision ID: 6acae65eaa75
Revises: e0a1b2c3d4e5
Create Date: 2026-09-21 03:43:23.878945

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6acae65eaa75'
down_revision: Union[str, Sequence[str], None] = 'e0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
