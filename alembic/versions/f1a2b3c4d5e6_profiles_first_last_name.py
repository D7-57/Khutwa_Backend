"""profiles: first_name + last_name (replace full_name when present)

Revision ID: f1a2b3c4d5e6
Revises: e7a1b2c3d4e5
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("profiles")}

    if "first_name" not in cols:
        op.add_column(
            "profiles",
            sa.Column("first_name", sa.String(length=80), nullable=True),
        )
    if "last_name" not in cols:
        op.add_column(
            "profiles",
            sa.Column("last_name", sa.String(length=80), nullable=True),
        )

    if "full_name" in cols:
        op.execute(
            sa.text(
                """
                UPDATE profiles SET
                  first_name = COALESCE(first_name, NULLIF(btrim(split_part(btrim(full_name), ' ', 1)), '')),
                  last_name = COALESCE(
                    last_name,
                    NULLIF(btrim(regexp_replace(btrim(full_name), '^[^\\s]+\\s*', '')), '')
                  )
                WHERE full_name IS NOT NULL AND btrim(full_name) <> '';
                """
            )
        )
        op.drop_column("profiles", "full_name")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("full_name", sa.String(length=120), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE profiles SET full_name = NULLIF(
              trim(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')),
              ''
            );
            """
        )
    )
    op.drop_column("profiles", "first_name")
    op.drop_column("profiles", "last_name")
