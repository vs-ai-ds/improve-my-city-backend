"""add email_from_name to app_settings

Revision ID: 8f7e6d5c4b3a
Revises: 193892d572b0
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f7e6d5c4b3a'
down_revision: Union[str, Sequence[str], None] = '193892d572b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('app_settings', sa.Column('email_from_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_settings', 'email_from_name')

