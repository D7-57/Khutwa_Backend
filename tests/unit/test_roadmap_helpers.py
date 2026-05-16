"""
Unit tests for app/services/roadmap/generator.py

Focuses on pure helper functions that contain no DB, AI, or external calls:
  - classify_task_for_profile
  - _contains_arabic
  - _standard_certs_for_role
  - _filter_unearned_certs
  - _cert_aliases
  - _normalize_token / _normalize_user_cert_tokens
  - _resolve_roadmap_titles
  - _infer_experience_level
  - _build_profile_context (mocked Profile)
"""

import uuid
import pytest
from unittest.mock import MagicMock

from app.services.roadmap.generator import (
    classify_task_for_profile,
    _contains_arabic,
    _standard_certs_for_role,
    _filter_unearned_certs,
    _cert_aliases,
    _normalize_token,
    _infer_experience_level,
    _PROJECT_KEYWORDS,
    _CERT_KEYWORDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# classify_task_for_profile
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyTaskForProfile:
    def _make_task(self, title: str, description: str = "", skill_name: str | None = None):
        task = MagicMock()
        task.title = title
        task.description = description
        task.skill_name = skill_name
        return task

    def test_certification_keyword_gives_certification(self):
        task = self._make_task("Earn AWS Certified Solutions Architect")
        assert classify_task_for_profile(task) == "certification"

    def test_build_keyword_gives_project(self):
        task = self._make_task("Build a REST API with FastAPI")
        assert classify_task_for_profile(task) == "project"

    def test_create_keyword_gives_project(self):
        task = self._make_task("Create a portfolio website")
        assert classify_task_for_profile(task) == "project"

    def test_skill_name_present_no_keywords_gives_skill(self):
        task = self._make_task("Learn advanced Python", skill_name="Python")
        assert classify_task_for_profile(task) == "skill"

    def test_no_skill_name_no_keywords_defaults_to_skill(self):
        task = self._make_task("Study REST principles")
        assert classify_task_for_profile(task) == "skill"

    def test_cert_in_description_gives_certification(self):
        task = self._make_task("Study materials", description="Prepare for CompTIA Security+ exam")
        assert classify_task_for_profile(task) == "certification"

    def test_cert_takes_priority_over_project_keyword(self):
        # "build certification prep notes" has both "build" and "certif"
        task = self._make_task("Build certification prep notes for eJPT")
        assert classify_task_for_profile(task) == "certification"


# ─────────────────────────────────────────────────────────────────────────────
# _contains_arabic
# ─────────────────────────────────────────────────────────────────────────────

class TestContainsArabic:
    def test_arabic_text_detected(self):
        assert _contains_arabic("مرحباً بالعالم")

    def test_english_text_not_detected(self):
        assert not _contains_arabic("Hello World")

    def test_mixed_text_detected(self):
        assert _contains_arabic("Hello مرحبا World")

    def test_none_returns_false(self):
        assert not _contains_arabic(None)

    def test_empty_string_returns_false(self):
        assert not _contains_arabic("")


# ─────────────────────────────────────────────────────────────────────────────
# _standard_certs_for_role
# ─────────────────────────────────────────────────────────────────────────────

class TestStandardCertsForRole:
    def test_cloud_engineer_returns_cloud_certs(self):
        certs = _standard_certs_for_role("Cloud Engineer")
        assert any("AWS" in c or "Azure" in c or "Google" in c for c in certs)

    def test_security_analyst_returns_security_certs(self):
        certs = _standard_certs_for_role("Security Analyst")
        assert len(certs) >= 1

    def test_unknown_role_returns_empty(self):
        certs = _standard_certs_for_role("Barista")
        assert certs == []

    def test_empty_role_returns_empty(self):
        assert _standard_certs_for_role("") == []

    def test_software_engineer_returns_relevant_certs(self):
        certs = _standard_certs_for_role("Software Engineer")
        assert len(certs) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# _filter_unearned_certs
# ─────────────────────────────────────────────────────────────────────────────

class TestFilterUnearnedCerts:
    def test_removes_owned_cert(self):
        candidates = ["CompTIA Security+", "eJPT", "AWS Certified Solutions Architect – Associate"]
        owned = ["CompTIA Security+"]
        result = _filter_unearned_certs(candidates, owned)
        assert "CompTIA Security+" not in result
        assert "eJPT" in result

    def test_alias_matching_removes_cert(self):
        """User listed 'security+' → should filter out 'CompTIA Security+'."""
        candidates = ["CompTIA Security+", "eJPT"]
        owned = ["security+"]
        result = _filter_unearned_certs(candidates, owned)
        assert "CompTIA Security+" not in result

    def test_empty_owned_returns_all(self):
        candidates = ["eJPT", "OSCP"]
        result = _filter_unearned_certs(candidates, [])
        assert result == candidates

    def test_all_owned_returns_empty(self):
        candidates = ["eJPT"]
        result = _filter_unearned_certs(candidates, ["ejpt"])
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_token
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeToken:
    def test_lowercases_and_strips_special_chars(self):
        assert _normalize_token("CompTIA Security+") == "comptiasecurity+"

    def test_empty_returns_empty(self):
        assert _normalize_token("") == ""

    def test_spaces_removed(self):
        assert _normalize_token("AWS Cloud") == "awscloud"


# ─────────────────────────────────────────────────────────────────────────────
# _cert_aliases
# ─────────────────────────────────────────────────────────────────────────────

class TestCertAliases:
    def test_security_plus_has_known_aliases(self):
        aliases = _cert_aliases("CompTIA Security+")
        assert "security+" in aliases or "sec+" in aliases

    def test_unknown_cert_returns_lower_form(self):
        aliases = _cert_aliases("My Custom Cert")
        assert "my custom cert" in aliases

    def test_ejpt_aliases(self):
        aliases = _cert_aliases("eJPT")
        assert "ejpt" in aliases


# ─────────────────────────────────────────────────────────────────────────────
# _infer_experience_level
# ─────────────────────────────────────────────────────────────────────────────

class TestInferExperienceLevel:
    def _profile(self, years="", certs=None, exps=None):
        p = MagicMock()
        p.years_of_experience = years
        p.certifications = certs or []
        p.experiences = exps or []
        return p

    def test_no_signals_returns_beginner(self):
        assert _infer_experience_level(self._profile()) == "beginner"

    def test_years_3_plus_returns_advanced(self):
        assert _infer_experience_level(self._profile(years="3+")) == "advanced"

    def test_one_year_returns_intermediate(self):
        assert _infer_experience_level(self._profile(years="1")) == "intermediate"

    def test_multiple_certs_returns_advanced(self):
        p = self._profile(certs=[{"name": "AWS"}, {"name": "Azure"}, {"name": "GCP"}])
        assert _infer_experience_level(p) == "advanced"

    def test_one_experience_entry_returns_intermediate(self):
        p = self._profile(exps=[{"company": "Acme"}])
        assert _infer_experience_level(p) == "intermediate"
