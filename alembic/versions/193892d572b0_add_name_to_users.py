"""add name to users

Revision ID: 193892d572b0
Revises: 22c6951eae57
Create Date: 2025-10-26 10:34:53.783414

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '193892d572b0'
down_revision: Union[str, Sequence[str], None] = '22c6951eae57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
