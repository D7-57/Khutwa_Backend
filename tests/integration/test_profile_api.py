"""
Integration tests for auth/profile endpoints.

Uses TestClient with:
  - in-memory SQLite (no Postgres needed)
  - mocked get_current_user_id (no real JWT validation)

Endpoints covered:
  GET  /auth/profile
  POST /auth/profile/basic-info
  PATCH /auth/profile
  GET  /health
"""

import pytest
import uuid
from tests.conftest import TEST_USER_ID


# ─────────────────────────────────────────────────────────────────────────────
# Health check (public, always-available baseline)
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_no_auth_needed(self, client_unauth):
        r = client_unauth.get("/health")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /auth/profile
# ─────────────────────────────────────────────────────────────────────────────

class TestGetProfile:
    def test_returns_profile_for_authenticated_user(self, client):
        # GET /auth/me — creates profile row on first access
        r = client.get("/auth/me")
        assert r.status_code == 200

    def test_profile_has_id_field(self, client):
        r = client.get("/auth/me")
        data = r.json()
        assert "id" in data

    def test_profile_id_matches_auth_user(self, client):
        r = client.get("/auth/me")
        data = r.json()
        assert data["id"] == TEST_USER_ID

    def test_unauthenticated_request_returns_401(self, client_unauth):
        r = client_unauth.get("/auth/me")
        assert r.status_code == 401

    def test_profile_response_is_json_object(self, client):
        r = client.get("/auth/me")
        assert isinstance(r.json(), dict)


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/onboarding/basic  (onboarding step)
# ─────────────────────────────────────────────────────────────────────────────

class TestBasicInfoOnboarding:
    def _valid_onboarding_payload(self):
        return {
            "first_name": "Ahmed",
            "last_name": "Rashidi",
            "major": "Computer Science",
            "university": "King Saud University",
            "graduation_year": 2024,
            "current_status": "fresh_graduate",
            "language": "en",
            "accept_terms": True,
            "terms_version": "v1",
        }

    def test_saves_basic_info_successfully(self, client):
        r = client.post("/auth/onboarding/basic", json=self._valid_onboarding_payload())
        assert r.status_code in (200, 201)

    def test_saved_name_is_retrievable(self, client):
        payload = {**self._valid_onboarding_payload(), "first_name": "Fatimah", "last_name": "Noor"}
        client.post("/auth/onboarding/basic", json=payload)
        r = client.get("/auth/me")
        data = r.json()
        assert data.get("first_name") == "Fatimah"

    def test_invalid_payload_returns_error_not_500(self, client):
        r = client.post("/auth/onboarding/basic", json={"language": 12345})
        assert r.status_code != 500


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /auth/me  (profile update)
# ─────────────────────────────────────────────────────────────────────────────

class TestPatchProfile:
    def test_patch_returns_200_or_204(self, client):
        r = client.patch("/auth/me", json={"language": "ar"})
        assert r.status_code in (200, 204)

    def test_updated_language_is_persisted(self, client):
        client.post("/auth/onboarding/basic", json={"first_name": "Test", "language": "en"})
        client.patch("/auth/me", json={"language": "ar"})
        r = client.get("/auth/me")
        assert r.json().get("language") == "ar"

    def test_unauthenticated_patch_returns_401(self, client_unauth):
        r = client_unauth.patch("/auth/me", json={"language": "en"})
        assert r.status_code == 401
