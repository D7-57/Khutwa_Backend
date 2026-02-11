import requests
import os
from dotenv import load_dotenv

# -----------------------
# CONFIG
# -----------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
API_URL = "http://127.0.0.1:8000"

EMAIL = "test@gmail.com"
PASSWORD = "QwQwQw12"


# -----------------------
# AUTH
# -----------------------
def get_token(email, password):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "email": email,
        "password": password,
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code != 200:
        print("❌ Login failed:", response.text)
        return None

    token = response.json()["access_token"]
    print("✅ Got access token")
    return token


# -----------------------
# TEST FLOW
# -----------------------
def main():
    token = get_token(EMAIL, PASSWORD)
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 1️⃣ Test /auth/me
    print("\n--- Testing /auth/me ---")
    r = requests.get(f"{API_URL}/auth/me", headers=headers)
    print("Status:", r.status_code)
    print("Response:", r.json())

    # 2️⃣ Start Interview
    print("\n--- Starting Interview ---")
    r = requests.post(
        f"{API_URL}/interviews/start",
        params={"role_name": "software_engineer", "num_questions": 3},
        headers=headers,
    )
    print("Status:", r.status_code)
    data = r.json()
    print("Response:", data)

    session_id = data["session_id"]
    question_id = data["question_id"]
    question_text = data["question_text"]

    # 3️⃣ Download Question Audio
    print("\n--- Downloading Question Audio ---")
    r = requests.get(
        f"{API_URL}/interviews/{session_id}/question-audio/{question_id}",
        headers=headers,
    )

    if r.status_code == 200:
        with open("question.mp3", "wb") as f:
            f.write(r.content)
        print("✅ Audio saved as question.mp3")
        print("Audio size:", len(r.content), "bytes")
    else:
        print("❌ Audio failed:", r.status_code, r.text)

    # 4️⃣ Submit Answer (TEXT)
    print("\n--- Submitting Answer ---")
    sample_answer = "REST is an architectural style for APIs that uses HTTP methods and stateless communication."

    r = requests.post(
        f"{API_URL}/interviews/{session_id}/answer",
        params={
            "question_id": question_id,
            "answer": sample_answer,
        },
        headers=headers,
    )

    print("Status:", r.status_code)
    print("Response:", r.json())

    # 5️⃣ Get Next Question
    print("\n--- Getting Next Question ---")
    r = requests.get(
        f"{API_URL}/interviews/{session_id}/next",
        headers=headers,
    )
    print("Status:", r.status_code)
    print("Response:", r.json())


if __name__ == "__main__":
    main()
