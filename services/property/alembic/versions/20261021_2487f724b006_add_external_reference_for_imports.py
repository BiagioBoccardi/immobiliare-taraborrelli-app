"""add external reference for imports

Code of the listing in the agency's management software, used by the Excel import.

Revision ID: 2487f724b006
Revises: 1251614c0e21
Create Date: 2026-10-21 09:06:21.375861

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '2487f724b006'
down_revision: str | None = '1251614c0e21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('properties', sa.Column('external_ref', sa.String(length=50), nullable=True))
    op.create_unique_constraint(op.f('uq_properties_external_ref'), 'properties', ['external_ref'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_properties_external_ref'), 'properties', type_='unique')
    op.drop_column('properties', 'external_ref')
