"""newRoles And Skills

Revision ID: 939a85dbf117
Revises: 33a99951e752
Create Date: 2026-05-12 00:09:39.170904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '939a85dbf117'
down_revision: Union[str, None] = '33a99951e752'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_IT_DOMAIN_NAMES = (
    "Software Engineering",
    "Data & AI",
    "Cybersecurity",
    "Networking & Cloud",
    "Information Systems & Business",
    "UX & Design",
)

_IT_DOMAIN_NAMES_SQL = ", ".join(f"'{n}'" for n in _IT_DOMAIN_NAMES)


def upgrade() -> None:
    # ── 1. Add new columns (nullable first so existing rows are not rejected) ──
    op.add_column(
        "roles",
        sa.Column(
            "role_type",
            sa.String(length=20),
            nullable=False,
            server_default="role",  # all existing rows → 'role' (correct for leaf roles)
        ),
    )
    op.add_column(
        "roles",
        sa.Column("name_en", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "roles",
        sa.Column("name_ar", sa.String(length=120), nullable=True),
    )

    # ── 2. Backfill name_en and name_ar from existing `name` ──────────────────
    op.execute("UPDATE roles SET name_en = name, name_ar = name")

    # ── 3. Make name_en / name_ar NOT NULL now that they're all populated ──────
    op.alter_column("roles", "name_en", nullable=False)
    op.alter_column("roles", "name_ar", nullable=False)

    # ── 4. Insert the "Information Technology" root field ─────────────────────
    # Use gen_random_uuid() (available on PostgreSQL >= 13 without extension).
    op.execute(
        """
        INSERT INTO roles (id, name, name_en, name_ar, description, role_type, parent_id, created_at)
        VALUES (
            gen_random_uuid(),
            'Information Technology',
            'Information Technology',
            'تقنية المعلومات',
            'Software, data, cybersecurity, and cloud disciplines.',
            'field',
            NULL,
            NOW()
        )
        """
    )

    # ── 5. Update the six IT domain rows ──────────────────────────────────────
    # They were parent_id=NULL and role_type='role' (default). Fix both.
    op.execute(
        f"""
        UPDATE roles
        SET
            role_type = 'domain',
            parent_id = (
                SELECT id FROM roles
                WHERE name = 'Information Technology' AND role_type = 'field'
            )
        WHERE
            parent_id IS NULL
            AND name IN ({_IT_DOMAIN_NAMES_SQL})
        """
    )


def downgrade() -> None:
    # ── Reverse step 5: detach IT domains back to root ────────────────────────
    op.execute(
        f"""
        UPDATE roles
        SET role_type = 'role', parent_id = NULL
        WHERE role_type = 'domain'
          AND name IN ({_IT_DOMAIN_NAMES_SQL})
        """
    )

    # ── Reverse step 4: remove the IT field row ───────────────────────────────
    op.execute(
        "DELETE FROM roles WHERE name = 'Information Technology' AND role_type = 'field'"
    )

    # ── Reverse step 3/2/1: drop new columns ──────────────────────────────────
    op.drop_column("roles", "name_ar")
    op.drop_column("roles", "name_en")
    op.drop_column("roles", "role_type")
