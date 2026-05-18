"""
Idempotent seed for the achievements catalog.

Run with:
    python -m seeds.achievements_seed

Matches the get_or_create pattern of seeds/questions_seed.py — re-running is
safe and only inserts rows whose `key` doesn't already exist. Use it for
fresh databases AND for picking up new achievements after edits below.

To rename an existing achievement, edit the title/description/icon/tier here
and re-run; only `key` is the immutable identifier. To remove one, delete
the dict entry below AND run a manual migration to drop the row (we don't
auto-delete on seed — keeping the row preserves user unlocks).
"""

from __future__ import annotations

import sys

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.achievement import Achievement


# Order in this list = default sort_order in the UI grid. Edit freely.
ACHIEVEMENTS: list[dict] = [
    # ── INTERVIEW ───────────────────────────────────────────────────
    {
        "key": "interview_first",
        "title_en": "First Steps",
        "title_ar": "الخطوة الأولى",
        "description_en": "Complete your first interview session.",
        "description_ar": "أكمل جلسة المقابلة الأولى.",
        "icon": "🎤",
        "tier": "bronze",
        "category": "interview",
    },
    {
        "key": "interview_5",
        "title_en": "Getting Warm",
        "title_ar": "الإحماء",
        "description_en": "Complete 5 interview sessions.",
        "description_ar": "أكمل 5 جلسات مقابلة.",
        "icon": "🔥",
        "tier": "bronze",
        "category": "interview",
    },
    {
        "key": "interview_10",
        "title_en": "Seasoned Speaker",
        "title_ar": "متحدث متمرس",
        "description_en": "Complete 10 interview sessions.",
        "description_ar": "أكمل 10 جلسات مقابلة.",
        "icon": "🎙️",
        "tier": "silver",
        "category": "interview",
    },
    {
        "key": "interview_50",
        "title_en": "Interview Marathoner",
        "title_ar": "ماراثون المقابلات",
        "description_en": "Complete 50 interview sessions.",
        "description_ar": "أكمل 50 جلسة مقابلة.",
        "icon": "🏃",
        "tier": "gold",
        "category": "interview",
    },
    {
        "key": "interview_score_90",
        "title_en": "High Achiever",
        "title_ar": "متفوّق",
        "description_en": "Finish an interview with a score of 90 or higher.",
        "description_ar": "أنهِ مقابلة بنتيجة 90 أو أعلى.",
        "icon": "⭐",
        "tier": "gold",
        "category": "interview",
    },
    {
        "key": "interview_perfect_100",
        "title_en": "Flawless Victory",
        "title_ar": "نصر مثالي",
        "description_en": "Score a perfect 100 in an interview.",
        "description_ar": "احصل على 100 كاملة في مقابلة.",
        "icon": "💯",
        "tier": "platinum",
        "category": "interview",
    },
    {
        "key": "interview_weekly_streak",
        "title_en": "On a Roll",
        "title_ar": "في عزّ التقدم",
        "description_en": "Complete 3 interviews within 7 days.",
        "description_ar": "أكمل 3 مقابلات خلال 7 أيام.",
        "icon": "📅",
        "tier": "silver",
        "category": "interview",
    },
    {
        "key": "interview_rapid_fire",
        "title_en": "Quick Draw",
        "title_ar": "ردّ سريع",
        "description_en": "Complete a rapid-fire interview round.",
        "description_ar": "أكمل جولة مقابلة سريعة.",
        "icon": "⚡",
        "tier": "silver",
        "category": "interview",
    },
    {
        "key": "interview_night_owl",
        "title_en": "Night Owl",
        "title_ar": "بومة الليل",
        "description_en": "Finish an interview between midnight and 4 AM.",
        "description_ar": "أنهِ مقابلة بين منتصف الليل والساعة 4 صباحًا.",
        "icon": "🦉",
        "tier": "gold",
        "category": "interview",
        "is_secret": True,
    },

    # ── CV ──────────────────────────────────────────────────────────
    {
        "key": "cv_first_upload",
        "title_en": "Paper Trail",
        "title_ar": "بداية السيرة",
        "description_en": "Upload your first CV.",
        "description_ar": "ارفع سيرتك الذاتية الأولى.",
        "icon": "📄",
        "tier": "bronze",
        "category": "cv",
    },
    {
        "key": "cv_ats_80",
        "title_en": "ATS Approved",
        "title_ar": "مُعتمَد من ATS",
        "description_en": "Score 80+ on an ATS check.",
        "description_ar": "احصل على 80 أو أكثر في فحص ATS.",
        "icon": "✅",
        "tier": "gold",
        "category": "cv",
    },
    {
        "key": "cv_polished",
        "title_en": "Polished",
        "title_ar": "مصقول",
        "description_en": "Use the AI enhancer 3 times on your CV.",
        "description_ar": "استخدم المُحسِّن الذكي 3 مرات على سيرتك.",
        "icon": "✨",
        "tier": "silver",
        "category": "cv",
    },

    # ── COMMUNITY ───────────────────────────────────────────────────
    {
        "key": "community_first",
        "title_en": "First Contribution",
        "title_ar": "أول مساهمة",
        "description_en": "Submit your first community question.",
        "description_ar": "أرسل أول سؤال للمجتمع.",
        "icon": "🌱",
        "tier": "bronze",
        "category": "community",
    },
    {
        "key": "community_star",
        "title_en": "Community Star",
        "title_ar": "نجم المجتمع",
        "description_en": "Get 5 community questions approved.",
        "description_ar": "احصل على الموافقة على 5 أسئلة مجتمعية.",
        "icon": "🌟",
        "tier": "gold",
        "category": "community",
    },
    {
        "key": "community_legend",
        "title_en": "Question Legend",
        "title_ar": "أسطورة الأسئلة",
        "description_en": "Get 20 community questions approved.",
        "description_ar": "احصل على الموافقة على 20 سؤالًا مجتمعيًا.",
        "icon": "👑",
        "tier": "platinum",
        "category": "community",
    },

    # ── ROADMAP ─────────────────────────────────────────────────────
    {
        "key": "roadmap_first_task",
        "title_en": "Step One",
        "title_ar": "الخطوة الأولى",
        "description_en": "Complete your first roadmap task.",
        "description_ar": "أكمل أول مهمة في خارطة الطريق.",
        "icon": "✔️",
        "tier": "bronze",
        "category": "roadmap",
    },
    {
        "key": "roadmap_pathfinder",
        "title_en": "Pathfinder",
        "title_ar": "مكتشف الطريق",
        "description_en": "Complete an entire roadmap stage.",
        "description_ar": "أكمل مرحلة كاملة من خارطة الطريق.",
        "icon": "🧭",
        "tier": "gold",
        "category": "roadmap",
    },

    # ── META ────────────────────────────────────────────────────────
    {
        "key": "meta_bilingual",
        "title_en": "Bilingual Brain",
        "title_ar": "عقل ثنائي اللغة",
        "description_en": "Switch languages mid-interview.",
        "description_ar": "بدّل اللغة أثناء المقابلة.",
        "icon": "🌐",
        "tier": "silver",
        "category": "meta",
        "is_secret": True,
    },
    {
        "key": "meta_jrs_gold",
        "title_en": "Gold Standard",
        "title_ar": "المعيار الذهبي",
        "description_en": "Reach a Job-Readiness Score of 80 or higher.",
        "description_ar": "اصل إلى مؤشر الجاهزية للعمل 80 أو أعلى.",
        "icon": "🥇",
        "tier": "gold",
        "category": "meta",
    },
    {
        "key": "meta_platinum_10",
        "title_en": "Achievement Hunter",
        "title_ar": "صيّاد الإنجازات",
        "description_en": "Unlock 10 achievements.",
        "description_ar": "افتح 10 إنجازات.",
        "icon": "🏆",
        "tier": "platinum",
        "category": "meta",
    },
]


def get_or_create(db: Session, key: str, defaults: dict) -> tuple[Achievement, bool]:
    """
    Returns (instance, created). If a row with this key exists, updates the
    presentation fields (title/description/icon/tier/category/is_secret/
    sort_order) so re-runs pick up edits to this file — but never touches
    the `id`, which would orphan user_achievements.
    """
    existing = db.query(Achievement).filter(Achievement.key == key).one_or_none()
    if existing is not None:
        # Refresh in-place so seed edits propagate.
        for k, v in defaults.items():
            if k == "key":
                continue
            setattr(existing, k, v)
        return existing, False

    inst = Achievement(key=key, **{k: v for k, v in defaults.items() if k != "key"})
    db.add(inst)
    return inst, True


def main() -> int:
    db: Session = SessionLocal()
    try:
        created_count = 0
        updated_count = 0
        for idx, row in enumerate(ACHIEVEMENTS):
            defaults = {
                "title_en": row["title_en"],
                "title_ar": row["title_ar"],
                "description_en": row["description_en"],
                "description_ar": row["description_ar"],
                "icon": row.get("icon", "🏆"),
                "tier": row.get("tier", "bronze"),
                "category": row["category"],
                "is_secret": row.get("is_secret", False),
                "sort_order": idx,
            }
            _, created = get_or_create(db, key=row["key"], defaults=defaults)
            if created:
                created_count += 1
            else:
                updated_count += 1
        db.commit()
        print(f"✓ achievements seeded — {created_count} new, {updated_count} updated")
        return 0
    except Exception as e:
        db.rollback()
        print(f"✗ seed failed: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())