"""fix community vote trigger logic

Revision ID: ddb6fce16975
Revises: c5a3710c04fb
Create Date: 2026-05-10 11:43:45.950421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddb6fce16975'
down_revision: Union[str, None] = 'c5a3710c04fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_recompute_question_status()
        RETURNS TRIGGER AS $$
        DECLARE
            q_status      TEXT;
            q_up          INTEGER;
            q_down        INTEGER;
            total         INTEGER;
            dislike_ratio NUMERIC;
        BEGIN
            SELECT status, upvotes, downvotes
                INTO q_status, q_up, q_down
                FROM questions
                WHERE id = NEW.question_id;

            IF q_status IS DISTINCT FROM 'pending' THEN
                RETURN NEW;
            END IF;

            total := q_up + q_down;

            IF total < 10 THEN
                RETURN NEW;
            END IF;

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

            -- No auto-approve: only AI quality_score approves.
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_recompute_question_status ON questions;
        CREATE TRIGGER trg_recompute_question_status
            AFTER UPDATE OF upvotes, downvotes ON questions
            FOR EACH ROW
            EXECUTE FUNCTION fn_recompute_question_status();
    """)


def downgrade() -> None:
    # Restore the OLD trigger logic
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_recompute_question_status()
        RETURNS TRIGGER AS $$
        DECLARE
            q_status TEXT; q_up INTEGER; q_down INTEGER;
            total INTEGER; ratio NUMERIC;
        BEGIN
            SELECT status, upvotes, downvotes
                INTO q_status, q_up, q_down
                FROM questions WHERE id = NEW.question_id;

            IF q_status IS DISTINCT FROM 'pending' THEN RETURN NEW; END IF;

            total := q_up + q_down;
            IF total < 5 THEN RETURN NEW; END IF;

            ratio := q_up::NUMERIC / total::NUMERIC;

            IF ratio >= 0.7 THEN
                UPDATE questions SET status = 'approved' WHERE id = NEW.question_id;
            ELSIF ratio <= 0.3 THEN
                UPDATE questions
                    SET status = 'rejected',
                        rejection_reason = COALESCE(rejection_reason, 'Rejected by community vote')
                    WHERE id = NEW.question_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_recompute_question_status ON questions;
        CREATE TRIGGER trg_recompute_question_status
            AFTER UPDATE OF upvotes, downvotes ON questions
            FOR EACH ROW
            EXECUTE FUNCTION fn_recompute_question_status();
    """)