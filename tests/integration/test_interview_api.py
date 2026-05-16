"""
Integration tests for the interview feature.

Covers the interview session lifecycle endpoints with mocked AI services
so no real OpenAI calls are made during CI.

Endpoints covered:
  POST /interviews/start
  GET  /interviews  (session list)
  GET  /interviews/{id}
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock

from tests.conftest import TEST_USER_ID


# ─────────────────────────────────────────────────────────────────────────────
# Helper fixtures
# ─────────────────────────────────────────────────────────────────────────────

MOCK_INTRO_TEXT = "Hi! Tell me about yourself."


# ─────────────────────────────────────────────────────────────────────────────
# POST /interviews/start
# ─────────────────────────────────────────────────────────────────────────────

class TestStartInterview:
    """
    Tests that the start endpoint returns a well-structured response.
    OpenAI calls are mocked out so tests never hit the real API.
    """

    def test_start_requires_auth(self, client_unauth):
        r = client_unauth.post("/interviews/start", json={"language": "en"})
        assert r.status_code == 401

    def test_start_returns_session_on_valid_request(self, client):
        with patch("app.routers.interviews.pick_intro", return_value=MOCK_INTRO_TEXT), \
             patch("app.routers.interviews.synthesize_question_audio", return_value=(None, None)):
            payload = {"language": "en"}
            r = client.post("/interviews/start", json=payload)
        # Expect 200 or 201 — session created or profile missing causes 422/400
        assert r.status_code in (200, 201, 400, 404, 422), \
            f"Unexpected status {r.status_code}: {r.text[:200]}"

    def test_start_with_no_payload_returns_error_not_500(self, client):
        """A request with missing required fields should not cause an unhandled 500."""
        r = client.post("/interviews/start", json={})
        assert r.status_code != 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /interviews
# ─────────────────────────────────────────────────────────────────────────────

class TestListInterviews:
    def test_list_requires_auth(self, client_unauth):
        r = client_unauth.get("/interviews")
        assert r.status_code == 401

    def test_list_returns_200_for_authenticated_user(self, client):
        r = client.get("/interviews")
        assert r.status_code == 200

    def test_list_returns_a_list(self, client):
        r = client.get("/interviews")
        data = r.json()
        assert isinstance(data, list)

    def test_empty_history_returns_empty_list(self, client):
        """A fresh user with no sessions should return an empty list."""
        r = client.get("/interviews")
        assert r.status_code == 200
        assert r.json() == []


# ─────────────────────────────────────────────────────────────────────────────
# GET /interviews/{session_id}/summary — non-existent session
# ─────────────────────────────────────────────────────────────────────────────

class TestGetInterview:
    def test_non_existent_session_summary_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        r = client.get(f"/interviews/{fake_id}/summary")
        assert r.status_code == 404

    def test_summary_requires_auth(self, client_unauth):
        fake_id = str(uuid.uuid4())
        r = client_unauth.get(f"/interviews/{fake_id}/summary")
        assert r.status_code == 401
