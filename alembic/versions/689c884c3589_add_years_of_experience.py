"""add years of experience

Revision ID: 689c884c3589
Revises: 922e856bc234
Create Date: 2026-04-29 22:29:30.601472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '689c884c3589'
down_revision: Union[str, None] = '922e856bc234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("years_of_experience", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "years_of_experience")
