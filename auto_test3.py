import os
import json
import requests
from dotenv import load_dotenv

# -----------------------
# CONFIG
# -----------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

EMAIL = os.getenv("TEST_EMAIL", "test@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "QwQwQw12")

OUTPUT_DIR = "cv_test_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------
# AUTH
# -----------------------
def get_token(email: str, password: str) -> str | None:
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
        print("❌ Login failed:")
        print(response.status_code, response.text)
        return None

    token = response.json()["access_token"]
    print("✅ Got access token")
    return token


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# -----------------------
# SAMPLE CV DATA
# Adjust fields if your Pydantic schema is stricter
# -----------------------
def build_sample_cv_payload() -> dict:
    return {
        "title": "Test CV Builder",
        "language": "en",
        "cv_data": {
            "contact_info": {
                "name": "Test User",
                "email": "test@gmail.com",
                "phone": "+966500000000",
                "location": "Riyadh, Saudi Arabia",
                "linkedin": "https://linkedin.com/in/testuser",
                "github": "https://github.com/testuser",
            },
            "summary": (
                "Computer science student interested in backend development, "
                "AI applications, and building practical products that solve real problems."
            ),
            "skills": [
                "Python",
                "FastAPI",
                "Flutter",
                "Supabase",
                "PostgreSQL",
                "SQLAlchemy",
                "Git",
            ],
            "experience": [
                {
                    "job_title": "Backend Intern",
                    "company": "Khutwa Labs",
                    "location": "Riyadh",
                    "start_date": "2025-06",
                    "end_date": "2025-08",
                    "description": [
                        "Built REST APIs using FastAPI and PostgreSQL.",
                        "Integrated Supabase Auth with backend authorization.",
                        "Worked on CV parsing and interview simulation features."
                    ]
                }
            ],
            "education": [
                {
                    "degree": "Bachelor of Computer Science",
                    "institution": "Example University",
                    "location": "Saudi Arabia",
                    "start_date": "2022",
                    "end_date": "2026",
                    "description": "Focused on software engineering and AI."
                }
            ],
            "projects": [
                {
                    "name": "Khutwa",
                    "description": (
                        "AI job readiness platform with CV builder, CV evaluation, "
                        "and interview simulation."
                    ),
                    "technologies": ["FastAPI", "Flutter", "Supabase", "OpenAI"],
                    "link": "https://github.com/testuser/khutwa"
                },
                {
                    "name": "CV Builder Test",
                    "description": "Testing HTML preview and PDF export pipeline.",
                    "technologies": ["Python", "Requests"],
                    "link": ""
                }
            ],
            "certifications": [
                {
                    "name": "AWS Cloud Practitioner",
                    "issuer": "Amazon",
                    "date": "2025-01"
                }
            ],
            "languages": [
                {"name": "Arabic", "level": "Native"},
                {"name": "English", "level": "Professional"}
            ]
        }
    }


# -----------------------
# API CALLS
# -----------------------
def get_templates(token: str):
    url = f"{API_URL}/cv/builder/templates"
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})

    print("\n📄 Templates status:", response.status_code)
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception:
        print(response.text)
        return None


def create_cv(token: str, payload: dict):
    url = f"{API_URL}/cv/builder"
    response = requests.post(url, headers=auth_headers(token), json=payload)

    print("\n🛠 Create CV status:", response.status_code)
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print(response.text)
        return None

    if response.status_code != 201:
        return None

    return data


def get_cv(token: str, cv_id: str):
    url = f"{API_URL}/cv/builder/{cv_id}"
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})

    print("\n📥 Get CV status:", response.status_code)
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception:
        print(response.text)
        return None


def preview_cv_html(token: str, cv_id: str, template: str = "classic"):
    url = f"{API_URL}/cv/builder/{cv_id}/preview"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"template": template},
    )

    print("\n👀 Preview HTML status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        return None

    html_path = os.path.join(OUTPUT_DIR, f"preview_{template}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"✅ HTML preview saved to: {html_path}")
    return html_path


def preview_cv_html_from_data(token: str, payload: dict, template: str = "classic"):
    url = f"{API_URL}/cv/builder/preview"

    preview_payload = {
        "template": template,
        "language": payload["language"],
        "cv_data": payload["cv_data"],
    }

    response = requests.post(url, headers=auth_headers(token), json=preview_payload)

    print("\n🧪 Preview-from-data HTML status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        return None

    html_path = os.path.join(OUTPUT_DIR, f"preview_from_data_{template}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"✅ Raw-data HTML preview saved to: {html_path}")
    return html_path


def export_cv_pdf(token: str, cv_id: str, template: str = "classic"):
    url = f"{API_URL}/cv/builder/{cv_id}/export/pdf"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"template": template},
    )

    print("\n📄 Export PDF status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        return None

    pdf_path = os.path.join(OUTPUT_DIR, f"cv_{template}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(response.content)

    print(f"✅ PDF saved to: {pdf_path}")
    return pdf_path


def save_json(filename: str, data: dict):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON saved to: {path}")


# -----------------------
# MAIN TEST FLOW
# -----------------------
def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
        return

    token = get_token(EMAIL, PASSWORD)
    if not token:
        return

    payload = build_sample_cv_payload()
    save_json("request_payload.json", payload)

    templates = get_templates(token)

    create_result = create_cv(token, payload)
    if not create_result:
        print("❌ CV creation failed")
        return

    cv_id = create_result["cv_id"]
    print(f"\n🆔 CV ID: {cv_id}")

    get_result = get_cv(token, cv_id)
    if get_result:
        save_json("saved_cv.json", get_result)

    # choose template
    selected_template = "classic"
    if isinstance(templates, list) and templates:
        first = templates[0]
        if isinstance(first, dict):
            selected_template = first.get("id", "classic")

    print(f"\n🎨 Using template: {selected_template}")

    preview_cv_html_from_data(token, payload, template=selected_template)
    preview_cv_html(token, cv_id, template=selected_template)
    export_cv_pdf(token, cv_id, template=selected_template)

    print("\n✅ CV builder test finished.")


if __name__ == "__main__":
    main()