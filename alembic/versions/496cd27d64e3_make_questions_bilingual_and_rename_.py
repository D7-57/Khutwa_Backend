"""make questions bilingual and rename language column

Revision ID: 496cd27d64e3
Revises: 74c1fb1fe0b0
Create Date: 2026-04-18 16:11:07.342627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '496cd27d64e3'
down_revision: Union[str, None] = '74c1fb1fe0b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) add new columns
    op.add_column("questions", sa.Column("question_text_en", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("question_text_ar", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("rejection_reason", sa.Text(), nullable=True))

    # 2) rename language -> original_language
    op.alter_column(
        "questions",
        "language",
        new_column_name="original_language",
        existing_type=sa.String(length=10),
        existing_nullable=False,
    )

    # 3) migrate existing question_text into the proper new language column
    op.execute("""
        UPDATE questions
        SET question_text_en = question_text
        WHERE original_language = 'en' OR original_language IS NULL
    """)

    op.execute("""
        UPDATE questions
        SET question_text_ar = question_text
        WHERE original_language = 'ar'
    """)

    # 4) drop old single-language text column
    op.drop_column("questions", "question_text")


def downgrade() -> None:
    # 1) bring back old column
    op.add_column("questions", sa.Column("question_text", sa.Text(), nullable=True))

    # 2) restore data into question_text from the original language
    op.execute("""
        UPDATE questions
        SET question_text =
            CASE
                WHEN original_language = 'ar' THEN question_text_ar
                ELSE question_text_en
            END
    """)

    # 3) rename original_language back to language
    op.alter_column(
        "questions",
        "original_language",
        new_column_name="language",
        existing_type=sa.String(length=10),
        existing_nullable=False,
    )

    # 4) drop new columns
    op.drop_column("questions", "rejection_reason")
    op.drop_column("questions", "question_text_ar")
    op.drop_column("questions", "question_text_en")