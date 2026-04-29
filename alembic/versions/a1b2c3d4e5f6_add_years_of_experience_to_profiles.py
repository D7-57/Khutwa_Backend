"""add years_of_experience to profiles

Revision ID: a1b2c3d4e5f6
Revises: 922e856bc234
Create Date: 2026-04-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "922e856bc234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("years_of_experience", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "years_of_experience")