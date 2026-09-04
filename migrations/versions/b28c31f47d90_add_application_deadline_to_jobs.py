"""add application_deadline to jobs

Revision ID: b28c31f47d90
Revises: e4a1b83d9f21
Create Date: 2026-09-04 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'b28c31f47d90'
down_revision = 'e4a1b83d9f21'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    job_cols = {c['name'] for c in insp.get_columns('jobs')}
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        if 'application_deadline' not in job_cols:
            batch_op.add_column(sa.Column('application_deadline', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('application_deadline')
