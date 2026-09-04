"""add scored_at to applications

Revision ID: 06f8b56be579
Revises: dc893b029219
Create Date: 2026-09-02 10:25:54.412531

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '06f8b56be579'
down_revision = 'dc893b029219'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scored_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_column('scored_at')
