"""add callback requests from the agency's website

Callback requests ("Richiedi di essere ricontattato") carry contact details only, so the
property fields become optional for them.

Revision ID: c4a1e7d2b9f3
Revises: 6b344c9582a9
Create Date: 2026-10-28 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c4a1e7d2b9f3'
down_revision: str | None = '6b344c9582a9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWNER_INTENTION = sa.Enum('know_value', 'planning', 'decided', name='owner_intention')
_PROPERTY_TYPE = sa.Enum(
    'apartment', 'house', 'villa', 'attic', 'commercial', 'land', 'other', name='property_type'
)


def upgrade() -> None:
    # A new enum value must be committed before any row can use it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE lead_kind ADD VALUE IF NOT EXISTS 'callback'")
    op.alter_column('leads', 'intention', existing_type=_OWNER_INTENTION, nullable=True)
    op.alter_column('leads', 'municipality', existing_type=sa.String(length=80), nullable=True)
    op.alter_column('leads', 'property_type', existing_type=_PROPERTY_TYPE, nullable=True)


def downgrade() -> None:
    # Callback requests cannot exist without the new columns' values: remove them first.
    op.execute("DELETE FROM leads WHERE kind = 'callback'")
    op.alter_column('leads', 'property_type', existing_type=_PROPERTY_TYPE, nullable=False)
    op.alter_column('leads', 'municipality', existing_type=sa.String(length=80), nullable=False)
    op.alter_column('leads', 'intention', existing_type=_OWNER_INTENTION, nullable=False)
    # PostgreSQL cannot drop a single enum value: rebuild the type without 'callback'.
    op.execute("ALTER TYPE lead_kind RENAME TO lead_kind_old")
    op.execute("CREATE TYPE lead_kind AS ENUM ('valuation', 'sell', 'rent')")
    op.execute(
        "ALTER TABLE leads ALTER COLUMN kind TYPE lead_kind USING kind::text::lead_kind"
    )
    op.execute("DROP TYPE lead_kind_old")
