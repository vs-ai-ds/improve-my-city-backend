"""add name to users

Revision ID: 22c6951eae57
Revises: 17bcc95440b9
Create Date: 2025-10-26 10:33:54.741329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22c6951eae57'
down_revision: Union[str, Sequence[str], None] = '17bcc95440b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
