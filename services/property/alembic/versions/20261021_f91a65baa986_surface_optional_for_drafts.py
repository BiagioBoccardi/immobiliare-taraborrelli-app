"""surface optional for drafts

Listings imported from an export without the surface are drafts until it is added.

Revision ID: f91a65baa986
Revises: 2487f724b006
Create Date: 2026-10-21 09:32:41.967526

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f91a65baa986'
down_revision: str | None = '2487f724b006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('properties', 'surface_sqm',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('properties', 'surface_sqm',
               existing_type=sa.INTEGER(),
               nullable=False)
