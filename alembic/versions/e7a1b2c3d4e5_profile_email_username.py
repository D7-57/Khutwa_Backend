"""add email and username to profiles

Revision ID: e7a1b2c3d4e5
Revises: 1468f9b6445d, d5746ca1adb3
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7a1b2c3d4e5"
down_revision: Union[str, tuple[str, str], None] = ("1468f9b6445d", "d5746ca1adb3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("username", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "username")
    op.drop_column("profiles", "email")
