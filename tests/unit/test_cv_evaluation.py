"""
Unit tests for app/services/cv_evaluation.py

Focuses on all deterministic helper functions that contain pure business
logic and need no database, no Supabase, and no real OpenAI calls.
"""

import pytest
from app.services.cv_evaluation import (
    _clamp_score,
    _contains_phrase,
    _flatten_skills,
    score_ats,
    build_overall_recommendations,
    build_radar_scores,
    _score_completeness,
    _score_experience_depth,
)


# ─────────────────────────────────────────────────────────────────────────────
# _clamp_score
# ─────────────────────────────────────────────────────────────────────────────

class TestClampScore:
    def test_within_range_returns_rounded_int(self):
        assert _clamp_score(72.6) == 73

    def test_zero_stays_zero(self):
        assert _clamp_score(0) == 0

    def test_100_stays_100(self):
        assert _clamp_score(100) == 100

    def test_negative_clamped_to_zero(self):
        assert _clamp_score(-15) == 0

    def test_above_100_clamped_to_100(self):
        assert _clamp_score(150) == 100


# ─────────────────────────────────────────────────────────────────────────────
# _contains_phrase
# ─────────────────────────────────────────────────────────────────────────────

class TestContainsPhrase:
    def test_exact_word_found(self):
        assert _contains_phrase("experienced python developer", "python")

    def test_word_boundary_respected(self):
        # "java" should not match "javascript"
        assert not _contains_phrase("javascript developer", "java")

    def test_case_insensitive(self):
        assert _contains_phrase("PYTHON is great", "python")

    def test_empty_phrase_returns_false(self):
        assert not _contains_phrase("some text", "")

    def test_phrase_not_in_text(self):
        assert not _contains_phrase("javascript react node", "python")

    def test_multi_word_phrase(self):
        assert _contains_phrase("machine learning engineer", "machine learning")


# ─────────────────────────────────────────────────────────────────────────────
# _flatten_skills
# ─────────────────────────────────────────────────────────────────────────────

class TestFlattenSkills:
    def test_list_input(self):
        result = _flatten_skills(["Python", "SQL", "React"])
        assert result == ["Python", "SQL", "React"]

    def test_dict_of_lists(self):
        result = _flatten_skills({"technical": ["Python", "SQL"], "soft": ["Communication"]})
        assert "Python" in result
        assert "SQL" in result
        assert "Communication" in result

    def test_none_returns_empty(self):
        assert _flatten_skills(None) == []

    def test_empty_list(self):
        assert _flatten_skills([]) == []

    def test_filters_blank_strings(self):
        result = _flatten_skills(["Python", "", "  "])
        assert result == ["Python"]


# ─────────────────────────────────────────────────────────────────────────────
# score_ats
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreAts:
    """Tests for the rule-based ATS scoring function (no AI calls)."""

    def _make_good_cv_text(self):
        return (
            "Jane Doe\nEmail: jane@example.com\nPhone: +966501234567\n\n"
            "Summary\nExperienced Software Engineer with 3 years of Python, React, Docker.\n\n"
            "Skills\nPython, React, Docker, SQL, Git, AWS\n\n"
            "Experience\nSoftware Engineer — Acme Corp | 2022 - 2024\n"
            "- Built REST APIs using FastAPI\n- Deployed containerized services on AWS\n\n"
            "Education\nBSc Computer Science, King Saud University | 2018 - 2022\n\n"
            "Projects\n- Personal portfolio website using React and Node.js\n"
            "- Data analysis tool using Python and pandas\n"
        )

    def test_good_cv_has_high_format_score(self):
        text = self._make_good_cv_text()
        role_profile = {"must_have_keywords": ["python", "react"], "nice_to_have_keywords": []}
        result = score_ats(text, {}, role_profile)
        # Score > empty CV (which gets heavy penalties for missing content)
        empty_result = score_ats("", {}, {})
        assert result["format_score"] > empty_result["format_score"], \
            "A well-formatted CV should score higher than an empty one"

    def test_score_keys_present(self):
        result = score_ats("Short text", {}, {})
        assert "score" in result
        assert "format_score" in result
        assert "keyword_score" in result
        assert "issues" in result
        assert "checklist" in result
        assert "matched_keywords" in result
        assert "missing_keywords" in result

    def test_scores_are_0_to_100(self):
        result = score_ats("", {}, {})
        assert 0 <= result["score"] <= 100
        assert 0 <= result["format_score"] <= 100
        assert 0 <= result["keyword_score"] <= 100

    def test_empty_cv_generates_issues(self):
        result = score_ats("", {}, {})
        assert len(result["issues"]) > 0

    def test_must_have_keywords_matched(self):
        text = "Experienced python developer with django background"
        role_profile = {
            "must_have_keywords": ["python", "django"],
            "nice_to_have_keywords": [],
        }
        result = score_ats(text, {}, role_profile)
        assert "python" in result["matched_keywords"]["must_have"]
        assert "django" in result["matched_keywords"]["must_have"]
        assert result["missing_keywords"]["must_have"] == []

    def test_missing_keyword_reported(self):
        text = "Frontend engineer with React experience"
        role_profile = {"must_have_keywords": ["python"], "nice_to_have_keywords": []}
        result = score_ats(text, {}, role_profile)
        assert "python" in result["missing_keywords"]["must_have"]

    def test_checklist_has_email_when_email_present(self):
        text = "Contact: john@test.com\nSkills\nExperience\n2020 - 2023"
        result = score_ats(text, {}, {})
        assert result["checklist"]["has_contact_info"] is True

    def test_table_formatting_penalised(self):
        text = "Name | Email | Phone | Skills | Years\n" * 5
        result = score_ats(text, {}, {})
        # Should detect table-like formatting
        assert result["checklist"]["likely_tables_or_columns"] is True


# ─────────────────────────────────────────────────────────────────────────────
# _score_completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreCompleteness:
    def test_full_checklist_gives_high_score(self):
        checklist = {
            "has_contact_info": True,
            "has_section_headings": True,
            "has_dates": True,
            "has_bullets": True,
            "has_experience": True,
            "has_education": True,
            "has_skills": True,
            "likely_tables_or_columns": False,
        }
        score = _score_completeness(checklist)
        assert score >= 80

    def test_empty_checklist_returns_50(self):
        assert _score_completeness({}) == 50

    def test_tables_penalises_score(self):
        checklist_no_table = {"has_contact_info": True}
        checklist_table = {"has_contact_info": True, "likely_tables_or_columns": True}
        assert _score_completeness(checklist_table) < _score_completeness(checklist_no_table)


# ─────────────────────────────────────────────────────────────────────────────
# _score_experience_depth
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreExperienceDepth:
    def test_no_signals_returns_around_50(self):
        score = _score_experience_depth({"role_fit": {}, "ats": {}})
        assert 40 <= score <= 65

    def test_experience_and_dates_boosts_score(self):
        eval_data = {
            "role_fit": {"strengths": ["Python", "FastAPI"], "gaps": []},
            "ats": {"checklist": {"has_experience": True, "has_dates": True, "has_bullets": True}},
        }
        score = _score_experience_depth(eval_data)
        assert score >= 65

    def test_many_gaps_lowers_score(self):
        eval_data_many_gaps = {
            "role_fit": {"strengths": [], "gaps": ["leadership", "cloud", "CI/CD", "k8s"]},
            "ats": {"checklist": {}},
        }
        eval_data_few_gaps = {
            "role_fit": {"strengths": [], "gaps": []},
            "ats": {"checklist": {}},
        }
        assert _score_experience_depth(eval_data_many_gaps) < _score_experience_depth(eval_data_few_gaps)


# ─────────────────────────────────────────────────────────────────────────────
# build_radar_scores
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildRadarScores:
    def test_returns_six_dimensions(self):
        eval_data = {
            "role_fit": {"score": 70, "strengths": ["Python"], "gaps": []},
            "ats": {
                "score": 80,
                "format_score": 85,
                "keyword_score": 75,
                "checklist": {"has_experience": True, "has_dates": True, "has_bullets": True},
            },
        }
        result = build_radar_scores(eval_data)
        expected_keys = {
            "ats_compatibility", "skills_relevance", "experience_depth",
            "keyword_coverage", "format_quality", "completeness",
        }
        assert set(result.keys()) == expected_keys

    def test_all_scores_0_to_100(self):
        eval_data = {"role_fit": {}, "ats": {}}
        result = build_radar_scores(eval_data)
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} is out of range"


# ─────────────────────────────────────────────────────────────────────────────
# build_overall_recommendations
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildOverallRecommendations:
    def test_returns_list(self):
        result = build_overall_recommendations({}, {})
        assert isinstance(result, list)

    def test_deduplication(self):
        ats = {
            "issues": [
                {"fix": "Use plain text email"},
                {"fix": "Use plain text email"},  # duplicate
                {"fix": "Add section headings"},
            ]
        }
        result = build_overall_recommendations({}, ats)
        assert len(result) == len(set(result))

    def test_pulls_from_ats_issues(self):
        ats = {"issues": [{"fix": "Add your email"}, {"fix": "Add headings"}]}
        result = build_overall_recommendations({}, ats)
        assert any("email" in r.lower() for r in result)

    def test_maximum_6_recommendations(self):
        ats = {"issues": [{"fix": f"Fix issue {i}"} for i in range(10)]}
        role_fit = {"gaps": [f"Gap {i}" for i in range(5)], "suggested_keywords": ["python", "sql", "git", "aws"]}
        result = build_overall_recommendations(role_fit, ats)
        assert len(result) <= 6
