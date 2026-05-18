"""
One-shot backfill — award achievements to users who already qualify.

Run this AFTER the migration + achievements seed. It loops over every profile
and fires every trigger once, so any user whose past activity already meets
an achievement's criteria gets credited.

The awards land with seen=False, so the very next time the user opens the app
the /achievements/unseen endpoint returns them and the overlay plays each one
through the queue (with the achievement sound).

Idempotent — safe to re-run. The check_and_award service skips keys the user
already owns. So if you change a predicate threshold later (e.g. drop
'interview_perfect_100' from 100 to 85), just re-run this and the newly
qualifying users get awarded immediately instead of waiting for their next
interview.

Run with:
    python -m seeds.backfill_achievements

Add --dry-run to preview without writing:
    python -m seeds.backfill_achievements --dry-run
"""

from __future__ import annotations

import sys

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.profile import Profile
from app.services.achievements import check_and_award


# Every backend trigger. We don't fire bilingual_switch / cv_enhance because
# those require client context that doesn't apply to historical state.
_BACKFILL_TRIGGERS = [
    "interview_complete",
    "cv_upload",
    "cv_evaluate",
    "community_submit",
    "roadmap_task",
    "jrs_update",
]


def main(dry_run: bool = False) -> int:
    db: Session = SessionLocal()
    try:
        users = db.query(Profile.id).all()
        total_users = len(users)
        total_awarded = 0
        print(f"→ backfilling {total_users} users across {len(_BACKFILL_TRIGGERS)} triggers...")

        for i, (user_id,) in enumerate(users, 1):
            per_user = 0
            for trigger in _BACKFILL_TRIGGERS:
                awarded = check_and_award(user_id, db, trigger=trigger)
                per_user += len(awarded)
            if per_user > 0:
                total_awarded += per_user
                print(f"  [{i:>4}/{total_users}] {user_id} → +{per_user}")

        if dry_run:
            db.rollback()
            print(f"✓ DRY RUN — {total_awarded} awards would have been inserted")
        else:
            db.commit()
            print(f"✓ backfill complete — {total_awarded} awards inserted")
        return 0
    except Exception as e:
        db.rollback()
        print(f"✗ backfill failed: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))
