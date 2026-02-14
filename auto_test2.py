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

token = get_token(EMAIL, PASSWORD)
print(token)