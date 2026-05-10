"""Hotfix vote trigger V2 again

Revision ID: 5a3e5db94ec2
Revises: ddb6fce16975
Create Date: 2026-05-10 12:52:50.171082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a3e5db94ec2'
down_revision: Union[str, None] = 'ddb6fce16975'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_recompute_question_status()
        RETURNS TRIGGER AS $$
        DECLARE
            total         INTEGER;
            dislike_ratio NUMERIC;
        BEGIN
            IF NEW.status IS DISTINCT FROM 'pending' THEN
                RETURN NEW;
            END IF;

            total := NEW.upvotes + NEW.downvotes;
            IF total < 10 THEN
                RETURN NEW;
            END IF;

            dislike_ratio := NEW.downvotes::NUMERIC / total::NUMERIC;

            IF dislike_ratio >= 0.6 THEN
                UPDATE questions
                    SET status = 'rejected',
                        rejection_reason = COALESCE(
                            rejection_reason,
                            'Rejected by community vote ('
                            || NEW.downvotes || '/' || total || ' dislikes)'
                        )
                    WHERE id = NEW.id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Restore the (broken) previous body. Kept only so down-migrations chain;
    # don't actually run this.
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_recompute_question_status()
        RETURNS TRIGGER AS $$
        DECLARE
            q_status TEXT; q_up INTEGER; q_down INTEGER;
            total INTEGER; dislike_ratio NUMERIC;
        BEGIN
            SELECT status, upvotes, downvotes
                INTO q_status, q_up, q_down
                FROM questions
                WHERE id = NEW.question_id;
            IF q_status IS DISTINCT FROM 'pending' THEN RETURN NEW; END IF;
            total := q_up + q_down;
            IF total < 10 THEN RETURN NEW; END IF;
            dislike_ratio := q_down::NUMERIC / total::NUMERIC;
            IF dislike_ratio >= 0.6 THEN
                UPDATE questions
                    SET status = 'rejected',
                        rejection_reason = COALESCE(
                            rejection_reason,
                            'Rejected by community vote (' || q_down || '/' || total || ' dislikes)'
                        )
                    WHERE id = NEW.question_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)