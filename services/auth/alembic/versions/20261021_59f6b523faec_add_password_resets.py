"""add password resets

Codes sent by email for "password dimenticata".

Revision ID: 59f6b523faec
Revises: 180d0a56904f
Create Date: 2026-10-21 10:24:57.149046

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '59f6b523faec'
down_revision: str | None = '180d0a56904f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('password_resets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_resets_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_resets'))
    )
    op.create_index(op.f('ix_password_resets_user_id'), 'password_resets', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_resets_user_id'), table_name='password_resets')
    op.drop_table('password_resets')
