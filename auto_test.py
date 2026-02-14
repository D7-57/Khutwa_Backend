import requests
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
API_URL = "http://127.0.0.1:8000"

EMAIL = "test@gmail.com"
PASSWORD = "QwQwQw12"


def get_token(email, password):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    data = {"email": email, "password": password}
    r = requests.post(url, json=data, headers=headers)
    r.raise_for_status()
    return r.json()["access_token"]


def answer_for(prompt: str) -> str:
    p = prompt.lower()
    if "oop" in p or "object-oriented" in p:
        return "OOP is a paradigm based on objects and classes. Key principles are encapsulation, inheritance, polymorphism, and abstraction. It helps with modularity, reuse, and maintainability."
    if "rest" in p or "api" in p:
        return "REST is an architectural style for web APIs. It is stateless, uses resources and HTTP methods like GET/POST/PUT/DELETE, and typically exchanges JSON."
    return "I would approach this by explaining the concept clearly and giving an example from a project."


def main():
    token = get_token(EMAIL, PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    print("\n--- START INTERVIEW ---")
    r = requests.post(
        f"{API_URL}/interviews/start",
        params={"role_name": "software_engineer", "num_questions": 3, "followup_max": 1},
        headers=headers,
    )
    data = r.json()
    print(data)

    session_id = data["session_id"]

    # INTRO
    print("\n--- INTRO TURN ---")
    intro_answer = "I am a software engineering student. I enjoy backend development and APIs. I built small projects using FastAPI and Postgres."
    r = requests.post(
        f"{API_URL}/interviews/{session_id}/turn",
        data={"answer_text": intro_answer},
        headers=headers,
    )
    data = r.json()
    print(data)

    # BANK LOOP
    while True:
        prompt = data.get("prompt_text", "")
        phase = data.get("phase")
        if phase == "outro" or phase == "finished":
            print("\n✅ DONE:", data.get("prompt_text"))
            break

        print("\nPROMPT:", prompt)
        ans = answer_for(prompt)
        print("ANSWER:", ans)

        r = requests.post(
            f"{API_URL}/interviews/{session_id}/turn",
            data={"answer_text": ans},
            headers=headers,
        )
        data = r.json()
        print(data)


if __name__ == "__main__":
    main()
