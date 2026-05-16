"""
Integration tests for the roadmap feature.

Tests roadmap CRUD and progress-tracking endpoints.
AI generation is mocked so no real OpenAI calls are made.

Endpoints covered:
  GET  /roadmap
  POST /roadmap/generate
  PATCH /roadmap/tasks/{task_id}/complete
  DELETE /roadmap/{id}
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock

from tests.conftest import TEST_USER_ID


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

MOCK_AI_ROADMAP = {
    "title": "Your Path to Software Development",
    "stages": [
        {
            "order": 1,
            "title": "Fundamentals",
            "description": "Learn core programming concepts.",
            "tasks": [
                {
                    "order": 1,
                    "title": "Learn Python basics",
                    "description": "Cover variables, loops, functions.",
                    "skill_name": "Python",
                    "resources": [],
                }
            ],
        }
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# GET /roadmap
# ─────────────────────────────────────────────────────────────────────────────

class TestGetRoadmap:
    def test_requires_auth(self, client_unauth):
        r = client_unauth.get("/roadmap/me")
        assert r.status_code == 401

    def test_returns_200_or_404_for_authenticated_user(self, client):
        r = client.get("/roadmap/me")
        assert r.status_code in (200, 404)

    def test_no_roadmap_returns_404_or_none(self, client):
        """A fresh user with no roadmap should get 404 or null body, not 500."""
        r = client.get("/roadmap/me")
        assert r.status_code in (200, 404)

    def test_all_roadmaps_endpoint(self, client):
        r = client.get("/roadmap/me/all")
        assert r.status_code in (200, 404)

    def test_all_roadmaps_requires_auth(self, client_unauth):
        r = client_unauth.get("/roadmap/me/all")
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# POST /roadmap/me/generate
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateRoadmap:
    def test_requires_auth(self, client_unauth):
        r = client_unauth.post("/roadmap/me/generate", json={"language": "en"})
        assert r.status_code == 401

    def test_returns_error_when_no_role_selected(self, client):
        """
        A user with no selected role should get a meaningful error (400/404/422),
        not an unhandled 500.
        """
        with patch("app.routers.roadmap.roadmap.generate_roadmap") as mock_gen:
            mock_gen.side_effect = ValueError("No role selected.")
            r = client.post("/roadmap/me/generate", json={"language": "en"})
        assert r.status_code in (400, 404, 422)

    def test_generate_with_mocked_service_returns_roadmap(self, client):
        """
        With a mocked generate_roadmap service, the endpoint should return
        a structured roadmap response.
        """
        from datetime import datetime, timezone
        mock_response = {
            "roadmap": {
                "id": str(uuid.uuid4()),
                "title": "Your Path to Software Development",
                "title_ar": "طريقك نحو التطوير",
                "role_id": None,
                "role_name": "Software Developer",
                "role_name_ar": "مطور برمجيات",
                "source": "ai",
                "is_ai_generated": True,
                "overall_progress": 0.0,
                "skill_focus": None,
                "include_tangible_outcome": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "stages": [],
            },
            "source": "ai",
            "skill_gap": [],
            "skills_matched": [],
            "previously_covered_skills": [],
        }
        with patch("app.routers.roadmap.roadmap.generate_roadmap", return_value=mock_response):
            r = client.post("/roadmap/me/generate", json={"language": "en"})
        assert r.status_code in (200, 201)
        data = r.json()
        assert "roadmap" in data or "source" in data


# ─────────────────────────────────────────────────────────────────────────────
# Task completion — PATCH /roadmap/me/tasks/{task_id}/complete
# ─────────────────────────────────────────────────────────────────────────────

class TestCompleteTask:
    def test_non_existent_task_returns_error(self, client):
        fake_task_id = str(uuid.uuid4())
        r = client.patch(f"/roadmap/me/tasks/{fake_task_id}/complete")
        assert r.status_code in (404, 400, 422)

    def test_requires_auth(self, client_unauth):
        fake_task_id = str(uuid.uuid4())
        r = client_unauth.patch(f"/roadmap/me/tasks/{fake_task_id}/complete")
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /roadmap/me/{roadmap_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteRoadmap:
    def test_non_existent_roadmap_returns_error(self, client):
        fake_id = str(uuid.uuid4())
        r = client.delete(f"/roadmap/me/{fake_id}")
        assert r.status_code in (404, 400, 204)

    def test_requires_auth(self, client_unauth):
        fake_id = str(uuid.uuid4())
        r = client_unauth.delete(f"/roadmap/me/{fake_id}")
        assert r.status_code == 401
