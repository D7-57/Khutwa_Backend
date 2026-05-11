"""merge new roles skills and roadmap skill focus

Revision ID: 3dcbefa5f2bc
Revises: 939a85dbf117, e250e1faf2d4
Create Date: 2026-05-12 00:30:29.789045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3dcbefa5f2bc'
down_revision: Union[str, None] = ('939a85dbf117', 'e250e1faf2d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
