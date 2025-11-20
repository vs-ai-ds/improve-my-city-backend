"""add settings fields for notifications sla branding

Adds SLA settings (sla_hours, sla_reminder_hours), branding fields (city_logo_url, support_email, website_url), 
and notification settings (auto_email_on_status_change, push_notifications_enabled) to app_settings table.

Revision ID: add_settings_fields
Revises: add_issue_type_fields
Create Date: 2025-01-20 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_settings_fields'
down_revision: Union[str, Sequence[str], None] = 'add_issue_type_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if auto_assign_issues exists, if not add it (it might have been added manually)
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='app_settings' AND column_name='auto_assign_issues'"))
    if result.fetchone() is None:
        op.add_column('app_settings', sa.Column('auto_assign_issues', sa.Boolean(), server_default='false', nullable=False))
    
    # Add new columns (with checks to avoid errors if they already exist)
    columns_to_add = [
        ('sla_hours', sa.Integer(), '48', False),
        ('sla_reminder_hours', sa.Integer(), '24', True),
        ('city_logo_url', sa.String(length=500), None, True),
        ('support_email', sa.String(length=255), None, True),
        ('website_url', sa.String(length=255), None, True),
        ('auto_email_on_status_change', sa.Boolean(), 'true', False),
        ('push_notifications_enabled', sa.Boolean(), 'true', False),
    ]
    
    for col_name, col_type, default, nullable in columns_to_add:
        result = conn.execute(sa.text(f"SELECT column_name FROM information_schema.columns WHERE table_name='app_settings' AND column_name='{col_name}'"))
        if result.fetchone() is None:
            if default:
                op.add_column('app_settings', sa.Column(col_name, col_type, server_default=default, nullable=nullable))
            else:
                op.add_column('app_settings', sa.Column(col_name, col_type, nullable=nullable))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_settings', 'push_notifications_enabled')
    op.drop_column('app_settings', 'auto_email_on_status_change')
    op.drop_column('app_settings', 'website_url')
    op.drop_column('app_settings', 'support_email')
    op.drop_column('app_settings', 'city_logo_url')
    op.drop_column('app_settings', 'sla_reminder_hours')
    op.drop_column('app_settings', 'sla_hours')

