"""sync all tables and columns safely

Revision ID: e4a1b83d9f21
Revises: 06f8b56be579
Create Date: 2026-09-04 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'e4a1b83d9f21'
down_revision = '06f8b56be579'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. admin_audit_logs
    if 'admin_audit_logs' not in existing_tables:
        op.create_table(
            'admin_audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('admin_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=60), nullable=False),
            sa.Column('entity_type', sa.String(length=30), nullable=True),
            sa.Column('entity_id', sa.Integer(), nullable=True),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
            batch_op.create_index('ix_admin_audit_logs_admin_id', ['admin_id'], unique=False)

    # 2. admin_settings
    if 'admin_settings' not in existing_tables:
        op.create_table(
            'admin_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=80), nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('label', sa.String(length=150), nullable=True),
            sa.Column('description', sa.String(length=300), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('updated_by_admin_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['updated_by_admin_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('admin_settings', schema=None) as batch_op:
            batch_op.create_index('ix_admin_settings_key', ['key'], unique=True)

    # 3. career_entries
    if 'career_entries' not in existing_tables:
        op.create_table(
            'career_entries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('entry_type', sa.String(length=20), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('organization', sa.String(length=200), nullable=True),
            sa.Column('location', sa.String(length=150), nullable=True),
            sa.Column('start_date', sa.String(length=50), nullable=True),
            sa.Column('end_date', sa.String(length=50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('credential_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['candidate_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('career_entries', schema=None) as batch_op:
            batch_op.create_index('ix_career_entries_candidate_id', ['candidate_id'], unique=False)

    # 4. notifications
    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=150), nullable=False),
            sa.Column('message', sa.String(length=300), nullable=False),
            sa.Column('link', sa.String(length=300), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['candidate_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('notifications', schema=None) as batch_op:
            batch_op.create_index('ix_notifications_candidate_id', ['candidate_id'], unique=False)

    # 5. saved_jobs
    if 'saved_jobs' not in existing_tables:
        op.create_table(
            'saved_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['candidate_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('candidate_id', 'job_id', name='uq_saved_job')
        )

    # 6. application_events
    if 'application_events' not in existing_tables:
        op.create_table(
            'application_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('note', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    # 7. support_tickets & support_ticket_messages
    if 'support_tickets' not in existing_tables:
        op.create_table(
            'support_tickets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('issue_type', sa.String(length=50), nullable=False),
            sa.Column('subject', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('attachment_filename', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('support_tickets', schema=None) as batch_op:
            batch_op.create_index('ix_support_tickets_status', ['status'], unique=False)
            batch_op.create_index('ix_support_tickets_user_id', ['user_id'], unique=False)

    if 'support_ticket_messages' not in existing_tables:
        op.create_table(
            'support_ticket_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('ticket_id', sa.Integer(), nullable=False),
            sa.Column('sender_id', sa.Integer(), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('attachment_filename', sa.String(length=255), nullable=True),
            sa.Column('is_admin_response', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('support_ticket_messages', schema=None) as batch_op:
            batch_op.create_index('ix_support_ticket_messages_ticket_id', ['ticket_id'], unique=False)

    # 8. Column checks on existing tables
    # Check users columns
    user_cols = {c['name'] for c in insp.get_columns('users')}
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'public_profile_enabled' not in user_cols:
            batch_op.add_column(sa.Column('public_profile_enabled', sa.Boolean(), nullable=True, server_default=sa.false()))
        if 'recruiter_discoverable' not in user_cols:
            batch_op.add_column(sa.Column('recruiter_discoverable', sa.Boolean(), nullable=True, server_default=sa.true()))
        if 'public_resume_enabled' not in user_cols:
            batch_op.add_column(sa.Column('public_resume_enabled', sa.Boolean(), nullable=True, server_default=sa.false()))

    # Check resumes columns
    resume_cols = {c['name'] for c in insp.get_columns('resumes')}
    with op.batch_alter_table('resumes', schema=None) as batch_op:
        if 'is_primary' not in resume_cols:
            batch_op.add_column(sa.Column('is_primary', sa.Boolean(), nullable=True, server_default=sa.false()))
        if 'updated_at' not in resume_cols:
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade():
    # Keep safe - drop tables in reverse dependency order if needed
    op.drop_table('support_ticket_messages', if_exists=True)
    op.drop_table('support_tickets', if_exists=True)
    op.drop_table('application_events', if_exists=True)
    op.drop_table('saved_jobs', if_exists=True)
    op.drop_table('notifications', if_exists=True)
    op.drop_table('career_entries', if_exists=True)
    op.drop_table('admin_settings', if_exists=True)
    op.drop_table('admin_audit_logs', if_exists=True)
