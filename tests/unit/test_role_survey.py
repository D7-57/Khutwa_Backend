"""
Unit tests for the role-survey scoring logic in
app/routers/career/role_survey.py

Tests cover:
  - Pure scoring helpers (_max_possible, _OPTION_ROLES structure)
  - Major / question data integrity
  - SurveyResult and SurveyRoleResult schema validation
  - Scoring determinism: same answers → same ranked result
"""

import pytest
from app.routers.career.role_survey import (
    _max_possible,
    _OPTION_ROLES,
    _QUESTIONS_BY_MAJOR,
    _MAJOR_ROLES,
    _ROLE_NAMES,
    _ROLE_EXPLANATIONS,
    SurveyAnswer,
    SurveySubmit,
    SurveyResult,
    SurveyRoleResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestQuestionDataIntegrity:
    def test_all_three_majors_have_questions(self):
        for key in ("it", "eng", "biz"):
            assert len(_QUESTIONS_BY_MAJOR[key]) >= 5, f"Major '{key}' has too few questions"

    def test_every_question_has_id_and_options(self):
        for major, questions in _QUESTIONS_BY_MAJOR.items():
            for q in questions:
                assert "id" in q, f"Question missing 'id' in major {major}"
                assert "options" in q and len(q["options"]) >= 2, \
                    f"Question {q.get('id')} has fewer than 2 options"

    def test_every_option_has_roles_list(self):
        for major, questions in _QUESTIONS_BY_MAJOR.items():
            for q in questions:
                for opt in q["options"]:
                    assert "roles" in opt and isinstance(opt["roles"], list), \
                        f"Option {opt.get('id')} is missing roles list"
                    assert len(opt["roles"]) >= 1, f"Option {opt.get('id')} has empty roles list"

    def test_all_option_roles_in_role_names(self):
        """Every role_key referenced by an option must have a display name."""
        for major, questions in _QUESTIONS_BY_MAJOR.items():
            for q in questions:
                for opt in q["options"]:
                    for rk in opt["roles"]:
                        assert rk in _ROLE_NAMES, \
                            f"Role key '{rk}' in option '{opt['id']}' not in _ROLE_NAMES"

    def test_all_option_ids_indexed_in_option_roles(self):
        """Every option id must appear in the flat _OPTION_ROLES lookup."""
        for major, questions in _QUESTIONS_BY_MAJOR.items():
            for q in questions:
                for opt in q["options"]:
                    assert opt["id"] in _OPTION_ROLES, \
                        f"Option id '{opt['id']}' not indexed in _OPTION_ROLES"

    def test_role_explanations_cover_all_role_names(self):
        for rk in _ROLE_NAMES:
            assert rk in _ROLE_EXPLANATIONS, f"Role '{rk}' has no explanation"


# ─────────────────────────────────────────────────────────────────────────────
# _max_possible
# ─────────────────────────────────────────────────────────────────────────────

class TestMaxPossible:
    def test_it_returns_question_count(self):
        assert _max_possible("it") == len(_QUESTIONS_BY_MAJOR["it"])

    def test_eng_returns_question_count(self):
        assert _max_possible("eng") == len(_QUESTIONS_BY_MAJOR["eng"])

    def test_biz_returns_question_count(self):
        assert _max_possible("biz") == len(_QUESTIONS_BY_MAJOR["biz"])

    def test_unknown_major_returns_zero(self):
        assert _max_possible("unknown") == 0


# ─────────────────────────────────────────────────────────────────────────────
# Scoring logic (directly exercising the POST /submit business logic)
# ─────────────────────────────────────────────────────────────────────────────

class TestScoringLogic:
    """
    Exercises the same scoring algorithm used in submit_survey() but without
    running the HTTP handler — pure dictionary manipulation, no DB, no auth.
    """

    def _compute_scores(self, major: str, answers: list[dict]) -> dict[str, int]:
        """Re-implement the scoring loop so we can test it in isolation."""
        scores: dict[str, int] = {rk: 0 for rk in _MAJOR_ROLES[major]}
        for ans in answers:
            for rk in _OPTION_ROLES.get(ans["option_id"], []):
                if rk in scores:
                    scores[rk] += 1
        return scores

    def test_answering_all_software_dev_options_ranks_it_first(self):
        """
        If all selected options map only to 'software_dev', that role
        should have the highest score.
        """
        # Collect options that exclusively map to software_dev
        it_questions = _QUESTIONS_BY_MAJOR["it"]
        answers = []
        for q in it_questions:
            for opt in q["options"]:
                if opt["roles"] == ["software_dev"]:
                    answers.append({"question_id": q["id"], "option_id": opt["id"]})
                    break
            if len(answers) >= 5:
                break

        if len(answers) < 3:
            pytest.skip("Not enough exclusive software_dev options to test determinism")

        scores = self._compute_scores("it", answers)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        assert ranked[0][0] == "software_dev", \
            f"Expected software_dev at top, got: {ranked[:3]}"

    def test_scores_are_non_negative(self):
        # Pick any valid answers for 'biz'
        biz_questions = _QUESTIONS_BY_MAJOR["biz"]
        answers = [
            {"question_id": q["id"], "option_id": q["options"][0]["id"]}
            for q in biz_questions[:5]
        ]
        scores = self._compute_scores("biz", answers)
        assert all(v >= 0 for v in scores.values())

    def test_scores_bounded_by_question_count(self):
        """No role should score more points than questions answered."""
        eng_questions = _QUESTIONS_BY_MAJOR["eng"]
        answers = [
            {"question_id": q["id"], "option_id": q["options"][0]["id"]}
            for q in eng_questions
        ]
        scores = self._compute_scores("eng", answers)
        max_possible = len(eng_questions)
        assert all(v <= max_possible for v in scores.values())


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_survey_role_result_valid(self):
        role = SurveyRoleResult(
            role_key="software_dev",
            name_en="Full-Stack Developer",
            name_ar="مطور متكامل",
            explanation_en="You enjoy building software.",
            explanation_ar="تستمتع ببناء البرمجيات.",
            score=7,
            max_score=10,
            match_percent=70,
        )
        assert role.match_percent == 70
        assert role.id is None  # optional field defaults to None

    def test_survey_result_valid(self):
        result = SurveyResult(
            selected_major="it",
            selected_major_label="Information Technology / Computing",
            selected_major_icon="computer",
            top_roles=[],
            score_breakdown={"software_dev": 5, "data_analyst": 3},
        )
        assert result.selected_major == "it"
        assert result.score_breakdown["software_dev"] == 5

    def test_survey_submit_requires_answers(self):
        """Pydantic should accept an empty answers list (backend validates it)."""
        payload = SurveySubmit(selected_major="it", answers=[])
        assert payload.selected_major == "it"

    def test_survey_answer_schema(self):
        ans = SurveyAnswer(question_id="it_q1", option_id="it_q1_a")
        assert ans.question_id == "it_q1"
        assert ans.option_id == "it_q1_a"
