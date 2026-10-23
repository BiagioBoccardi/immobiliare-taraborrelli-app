"""add 3d model to properties

Optional 3D model (binary glTF) of a property, uploaded from the admin panel.

Revision ID: 3b982c227ccb
Revises: f91a65baa986
Create Date: 2026-10-23 15:28:47.654436

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '3b982c227ccb'
down_revision: str | None = 'f91a65baa986'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('properties', sa.Column('three_d_model_key', sa.String(length=200), nullable=True))
    op.add_column('properties', sa.Column('three_d_model_size', sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f('uq_properties_three_d_model_key'), 'properties', ['three_d_model_key'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_properties_three_d_model_key'), 'properties', type_='unique')
    op.drop_column('properties', 'three_d_model_size')
    op.drop_column('properties', 'three_d_model_key')
