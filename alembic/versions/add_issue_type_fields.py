"""add issue_type description color display_order

Adds description, color, and display_order fields to issue_types table for enhanced issue type management.

Revision ID: add_issue_type_fields
Revises: 8f7e6d5c4b3a
Create Date: 2025-01-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_issue_type_fields'
down_revision: Union[str, Sequence[str], None] = '8f7e6d5c4b3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('issue_types', sa.Column('description', sa.String(length=500), nullable=True))
    op.add_column('issue_types', sa.Column('color', sa.String(length=7), nullable=True))
    op.add_column('issue_types', sa.Column('display_order', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('issue_types', 'display_order')
    op.drop_column('issue_types', 'color')
    op.drop_column('issue_types', 'description')
