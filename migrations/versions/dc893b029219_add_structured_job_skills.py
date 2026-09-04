"""add structured required/preferred skills fields to jobs

Revision ID: dc893b029219
Revises: c3780235b89b
Create Date: 2026-09-02 09:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc893b029219'
down_revision = 'c3780235b89b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('required_skills_raw', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('preferred_skills_raw', sa.Text(), nullable=True))

    # Drop the server_default now that existing rows are backfilled with '';
    # new inserts go through the model/form, which always supplies a value.
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('required_skills_raw', server_default=None)


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('preferred_skills_raw')
        batch_op.drop_column('required_skills_raw')
