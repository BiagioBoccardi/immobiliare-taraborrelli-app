"""add 3d version of room photos

Optional 3D version (binary glTF) of the room shown in each photo.

Revision ID: e4ec1715fefe
Revises: 3b982c227ccb
Create Date: 2026-10-23 23:01:04.704531

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e4ec1715fefe'
down_revision: str | None = '3b982c227ccb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('photos', sa.Column('three_d_key', sa.String(length=200), nullable=True))
    op.add_column('photos', sa.Column('three_d_size', sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f('uq_photos_three_d_key'), 'photos', ['three_d_key'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_photos_three_d_key'), 'photos', type_='unique')
    op.drop_column('photos', 'three_d_size')
    op.drop_column('photos', 'three_d_key')
