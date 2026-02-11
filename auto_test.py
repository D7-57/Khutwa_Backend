import requests

SUPABASE_URL = "https://.supabase.co/"
SUPABASE_KEY = ".."


def get_token(email, password):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    data = {"email": email, "password": password}

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print("Access Token:", response.json().get("access_token"))
        return response.json().get("access_token")
    else:
        print("Error:", response.json())


t = get_token("test@gmail.com", "QwQwQw12")


# Use the fresh token from your curl command
TOKEN = t
URL = "http://127.0.0.1:8000/auth/me"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

response = requests.get(URL, headers=headers)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
