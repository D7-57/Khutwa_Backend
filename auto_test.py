import os
import sys
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

EMAIL = os.getenv("TEST_EMAIL", "test@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "QwQwQw12")

TIMEOUT = 30


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────

def fail(msg: str):
    print(f"\n❌ FAIL: {msg}")
    sys.exit(1)


def ok(msg: str):
    print(f"✅ {msg}")


def info(msg: str):
    print(f"\n--- {msg} ---")


def pretty(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def assert_status(resp: requests.Response, expected: int, label: str):
    if resp.status_code != expected:
        print(f"\n❌ {label} returned {resp.status_code}, expected {expected}")
        try:
            pretty(resp.json())
        except Exception:
            print(resp.text)
        sys.exit(1)


def get_token(email: str, password: str) -> str:
    if not SUPABASE_URL or not SUPABASE_KEY:
        fail("SUPABASE_URL or SUPABASE_ANON_KEY is missing in .env")

    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "email": email,
        "password": password,
    }

    resp = requests.post(url, json=data, headers=headers, timeout=TIMEOUT)
    assert_status(resp, 200, "Supabase login")

    token = resp.json().get("access_token")
    if not token:
        fail("No access_token returned from Supabase")

    return token


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
    }


def answer_for(prompt: str) -> str:
    p = (prompt or "").lower()

    if "introduce yourself" in p or "tell me about yourself" in p or "عرّفني بنفسك" in p:
        return (
            "I am a software engineering student interested in backend development, "
            "APIs, and databases. I built small projects using FastAPI, PostgreSQL, "
            "and Supabase, and I enjoy solving practical problems."
        )

    if "oop" in p or "object-oriented" in p:
        return (
            "OOP is a programming paradigm based on classes and objects. "
            "Its core principles are encapsulation, inheritance, polymorphism, "
            "and abstraction. It helps organize code and improve maintainability."
        )

    if "rest" in p or "api" in p:
        return (
            "REST is an architectural style for web APIs. It is stateless, uses "
            "resources identified by URLs, and relies on HTTP methods like GET, "
            "POST, PUT, PATCH, and DELETE."
        )

    if "database" in p or "sql" in p:
        return (
            "A relational database stores data in tables with relationships. "
            "SQL is used to query and manage that data, and indexing helps improve performance."
        )

    if "project" in p:
        return (
            "One project I worked on involved building backend APIs with FastAPI, "
            "handling authentication, and designing database models."
        )

    return (
        "I would answer by defining the concept clearly, giving one practical example, "
        "and mentioning tradeoffs when relevant."
    )


# ─────────────────────────────────────────
#  TEST 1: HEALTH CHECK
# ─────────────────────────────────────────

def test_root():
    info("TEST ROOT")
    resp = requests.get(f"{API_URL}/", timeout=TIMEOUT)
    if resp.status_code not in (200, 304):
        fail(f"Root endpoint failed with status {resp.status_code}")
    ok("Root endpoint reachable")


# ─────────────────────────────────────────
#  TEST 2: INTERVIEW FLOW
# ─────────────────────────────────────────

def test_interview_flow(headers: dict):
    info("TEST INTERVIEW FLOW")

    start_body = {
        "role_name": "software_engineer",
        "num_questions": 3,
        "followup_max": 1,
        "question_source": "bank",   # bank | ai | mix
        "tech_ratio": 50,
        "company": None,
        "use_cv": False,
    }

    resp = requests.post(
        f"{API_URL}/interviews/start",
        json=start_body,
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "/interviews/start")

    data = resp.json()
    pretty(data)

    session_id = data.get("session_id")
    phase = data.get("phase")
    prompt_text = data.get("prompt_text")

    if not session_id:
        fail("Interview start did not return session_id")
    if phase != "intro":
        fail(f"Expected intro phase, got {phase}")

    ok("Interview session created")

    # answer intro
    intro_answer = answer_for(prompt_text)
    resp = requests.post(
        f"{API_URL}/interviews/{session_id}/turn",
        data={"answer_text": intro_answer},
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "Intro turn")

    data = resp.json()
    pretty(data)

    if data.get("phase") not in ("bank", "outro"):
        fail(f"Unexpected phase after intro: {data.get('phase')}")

    # loop through bank / followups until outro or finished
    turns = 0
    max_turns = 20
    last_question_id = data.get("question_id")

    while turns < max_turns:
        turns += 1

        phase = data.get("phase")
        prompt = data.get("prompt_text", "")
        prompt_type = data.get("prompt_type")
        action = data.get("action")

        if phase in ("outro", "finished"):
            ok(f"Interview reached terminal phase: {phase}")
            break

        print(f"\nTurn #{turns}")
        print("phase:", phase)
        print("prompt_type:", prompt_type)
        print("action:", action)
        print("prompt:", prompt)

        ans = answer_for(prompt)
        print("answer:", ans)

        resp = requests.post(
            f"{API_URL}/interviews/{session_id}/turn",
            data={"answer_text": ans},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert_status(resp, 200, f"Interview turn #{turns}")

        data = resp.json()
        pretty(data)

        # keep one valid question_id for audio test if available
        if data.get("question_id"):
            last_question_id = data["question_id"]

    else:
        fail("Interview loop exceeded max_turns")

    # summary endpoint
    info("TEST INTERVIEW SUMMARY")
    resp = requests.get(
        f"{API_URL}/interviews/{session_id}/summary",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "Interview summary")
    summary_data = resp.json()
    pretty(summary_data)
    ok("Interview summary fetched")

    # list interviews
    info("TEST LIST MY INTERVIEWS")
    resp = requests.get(
        f"{API_URL}/interviews",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "List interviews")
    list_data = resp.json()
    pretty(list_data)

    found = any(x.get("session_id") == session_id for x in list_data)
    if not found:
        fail("Created interview session not found in GET /interviews")

    ok("Interview appears in GET /interviews")

    # question audio endpoint
    if last_question_id:
        info("TEST QUESTION AUDIO")
        resp = requests.get(
            f"{API_URL}/interviews/{session_id}/question-audio/{last_question_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert_status(resp, 200, "Question audio")
        content_type = resp.headers.get("content-type", "")
        if "audio" not in content_type:
            fail(f"Expected audio content-type, got {content_type}")
        ok("Question audio endpoint works")
    else:
        print("⚠️ Skipping audio test because no question_id was captured")


# ─────────────────────────────────────────
#  TEST 3: COMMUNITY QUESTIONS FLOW
# ─────────────────────────────────────────

def test_community_questions_flow(headers: dict):
    info("TEST COMMUNITY QUESTIONS FLOW")

    suffix = random.randint(1000, 9999)

    submit_body = {
        "role_name": "software_engineer",
        "company": "TestCompany",
        "language": "en",
        "questions": [
            {
                "question_text": f"What is dependency injection in FastAPI? #{suffix}",
                "question_type": "technical",
                "difficulty": 3,
            },
            {
                "question_text": f"How do you handle conflict in a development team? #{suffix}",
                "question_type": "behavioral",
                "difficulty": 2,
            },
        ],
    }

    # submit
    resp = requests.post(
        f"{API_URL}/questions/community",
        json=submit_body,
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 201, "Submit community questions")

    created = resp.json()
    pretty(created)

    if not isinstance(created, list) or len(created) != 2:
        fail("Expected 2 created community questions")

    q1_id = created[0]["id"]
    q2_id = created[1]["id"]

    ok("Community questions submitted")

    # list mine
    info("TEST LIST MY COMMUNITY QUESTIONS")
    resp = requests.get(
        f"{API_URL}/questions/community",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "List my community questions")

    mine = resp.json()
    pretty(mine)

    mine_ids = {q["id"] for q in mine}
    if q1_id not in mine_ids or q2_id not in mine_ids:
        fail("Submitted questions not found in my list")

    ok("Submitted questions found in my list")

    # filter by pending
    info("TEST LIST MY COMMUNITY QUESTIONS WITH STATUS")
    resp = requests.get(
        f"{API_URL}/questions/community",
        params={"status": "pending"},
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "List my pending community questions")
    pending = resp.json()
    pretty(pending)
    ok("Pending filter works")

    # update one
    info("TEST UPDATE MY COMMUNITY QUESTION")
    update_body = {
        "question_text": f"Explain dependency injection in FastAPI with an example. #{suffix}",
        "difficulty": 4,
    }

    resp = requests.patch(
        f"{API_URL}/questions/community/{q1_id}",
        json=update_body,
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "Update community question")

    updated = resp.json()
    pretty(updated)

    if updated["question_text"] != update_body["question_text"]:
        fail("Question text was not updated")
    if updated["difficulty"] != 4:
        fail("Difficulty was not updated")

    ok("Community question updated")

    # delete the other one
    info("TEST DELETE MY COMMUNITY QUESTION")
    resp = requests.delete(
        f"{API_URL}/questions/community/{q2_id}",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 204, "Delete community question")
    ok("Community question deleted")

    # confirm deletion
    resp = requests.get(
        f"{API_URL}/questions/community",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "Re-list after deletion")
    mine_after_delete = resp.json()
    pretty(mine_after_delete)

    mine_after_ids = {q["id"] for q in mine_after_delete}
    if q2_id in mine_after_ids:
        fail("Deleted question still appears in my list")

    ok("Deletion confirmed")

    # browse approved
    info("TEST BROWSE APPROVED COMMUNITY QUESTIONS")
    resp = requests.get(
        f"{API_URL}/questions/community/browse",
        params={"role_name": "software_engineer"},
        headers=headers,
        timeout=TIMEOUT,
    )
    assert_status(resp, 200, "Browse approved community questions")

    browse_data = resp.json()
    pretty(browse_data)
    ok("Browse endpoint reachable")


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

def main():
    info("AUTH")
    token = get_token(EMAIL, PASSWORD)
    headers = auth_headers(token)
    ok("Authenticated successfully")

    test_root()
    test_interview_flow(headers)
    test_community_questions_flow(headers)

    print("\n🎉 ALL TESTS PASSED")


if __name__ == "__main__":
    main()