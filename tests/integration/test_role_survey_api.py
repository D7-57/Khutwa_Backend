"""
Integration tests for the role-survey API endpoints.

Uses FastAPI TestClient with in-memory SQLite (see conftest.py).
No real database, Supabase, or OpenAI calls are needed for these tests
because the role-survey endpoints work entirely from in-memory data.

Endpoints covered:
  GET  /career/role-survey/majors
  GET  /career/role-survey/questions?major=…
  POST /career/role-survey/submit
"""

import pytest
from app.routers.career.role_survey import _QUESTIONS_BY_MAJOR


# ─────────────────────────────────────────────────────────────────────────────
# GET /career/role-survey/majors
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMajors:
    def test_returns_200(self, client):
        r = client.get("/career/role-survey/majors")
        assert r.status_code == 200

    def test_returns_three_majors(self, client):
        r = client.get("/career/role-survey/majors")
        data = r.json()
        assert "majors" in data
        assert len(data["majors"]) == 3

    def test_major_has_required_fields(self, client):
        r = client.get("/career/role-survey/majors")
        for major in r.json()["majors"]:
            assert "key" in major
            assert "label_en" in major
            assert "icon" in major

    def test_major_keys_are_it_eng_biz(self, client):
        r = client.get("/career/role-survey/majors")
        keys = {m["key"] for m in r.json()["majors"]}
        assert keys == {"it", "eng", "biz"}

    def test_no_auth_required(self, client_unauth):
        """Majors endpoint should be public — no token needed."""
        r = client_unauth.get("/career/role-survey/majors")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /career/role-survey/questions?major=…
# ─────────────────────────────────────────────────────────────────────────────

class TestGetQuestions:
    @pytest.mark.parametrize("major", ["it", "eng", "biz"])
    def test_returns_200_for_all_valid_majors(self, client, major):
        r = client.get(f"/career/role-survey/questions?major={major}")
        assert r.status_code == 200

    def test_returns_questions_list(self, client):
        r = client.get("/career/role-survey/questions?major=it")
        data = r.json()
        assert "questions" in data
        assert isinstance(data["questions"], list)
        assert len(data["questions"]) > 0

    def test_total_matches_question_count(self, client):
        r = client.get("/career/role-survey/questions?major=it")
        data = r.json()
        assert data["total"] == len(data["questions"])

    def test_question_has_id_and_options(self, client):
        r = client.get("/career/role-survey/questions?major=eng")
        for q in r.json()["questions"]:
            assert "id" in q
            assert "text_en" in q
            assert "options" in q

    def test_each_option_has_roles(self, client):
        r = client.get("/career/role-survey/questions?major=biz")
        for q in r.json()["questions"]:
            for opt in q["options"]:
                assert "id" in opt
                assert "roles" in opt

    def test_invalid_major_returns_422(self, client):
        r = client.get("/career/role-survey/questions?major=medicine")
        assert r.status_code == 422

    def test_missing_major_param_returns_422(self, client):
        r = client.get("/career/role-survey/questions")
        assert r.status_code == 422

    def test_no_auth_required(self, client_unauth):
        r = client_unauth.get("/career/role-survey/questions?major=it")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /career/role-survey/submit
# ─────────────────────────────────────────────────────────────────────────────

def _it_payload(n_questions: int = 10):
    """Build a valid IT survey payload by picking the first option of each question."""
    questions = _QUESTIONS_BY_MAJOR["it"]
    answers = [
        {"question_id": q["id"], "option_id": q["options"][0]["id"]}
        for q in questions[:n_questions]
    ]
    return {"selected_major": "it", "answers": answers}


def _biz_payload():
    questions = _QUESTIONS_BY_MAJOR["biz"]
    answers = [
        {"question_id": q["id"], "option_id": q["options"][0]["id"]}
        for q in questions
    ]
    return {"selected_major": "biz", "answers": answers}


class TestSubmitSurvey:
    def test_returns_200_for_valid_submission(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        assert r.status_code == 200

    def test_response_has_required_top_level_fields(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        data = r.json()
        assert "selected_major" in data
        assert "top_roles" in data
        assert "score_breakdown" in data

    def test_top_roles_is_list(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        assert isinstance(r.json()["top_roles"], list)

    def test_top_roles_have_required_fields(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        for role in r.json()["top_roles"]:
            assert "role_key" in role
            assert "name_en" in role
            assert "score" in role
            assert "match_percent" in role

    def test_match_percent_is_0_to_100(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        for role in r.json()["top_roles"]:
            assert 0 <= role["match_percent"] <= 100

    def test_selected_major_echoed_back(self, client):
        r = client.post("/career/role-survey/submit", json=_it_payload())
        assert r.json()["selected_major"] == "it"

    def test_biz_survey_returns_biz_roles(self, client):
        r = client.post("/career/role-survey/submit", json=_biz_payload())
        assert r.status_code == 200
        role_keys = [role["role_key"] for role in r.json()["top_roles"]]
        biz_role_keys = {"financial", "marketing", "biz_coord", "biz_analyst", "operations", "hr"}
        assert any(rk in biz_role_keys for rk in role_keys)

    def test_returns_401_without_auth_token(self, client_unauth):
        r = client_unauth.post("/career/role-survey/submit", json=_it_payload())
        assert r.status_code == 401

    def test_empty_answers_returns_400(self, client):
        payload = {"selected_major": "it", "answers": []}
        r = client.post("/career/role-survey/submit", json=payload)
        assert r.status_code == 400

    def test_invalid_major_returns_422(self, client):
        payload = {"selected_major": "xyz", "answers": [{"question_id": "q1", "option_id": "o1"}]}
        r = client.post("/career/role-survey/submit", json=payload)
        assert r.status_code in (422, 400)

    def test_duplicate_answers_return_422(self, client):
        questions = _QUESTIONS_BY_MAJOR["it"]
        q = questions[0]
        payload = {
            "selected_major": "it",
            "answers": [
                {"question_id": q["id"], "option_id": q["options"][0]["id"]},
                {"question_id": q["id"], "option_id": q["options"][1]["id"]},  # duplicate question
            ],
        }
        r = client.post("/career/role-survey/submit", json=payload)
        assert r.status_code == 422

    def test_consistent_results_for_same_answers(self, client):
        """Same answers submitted twice must return same top role."""
        payload = _it_payload()
        r1 = client.post("/career/role-survey/submit", json=payload)
        r2 = client.post("/career/role-survey/submit", json=payload)
        assert r1.json()["top_roles"][0]["role_key"] == r2.json()["top_roles"][0]["role_key"]
