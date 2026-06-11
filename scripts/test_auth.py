import os
import sys
import secrets

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ENVIRONMENT"] = "development"
if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = secrets.token_hex(32)

from fastapi.testclient import TestClient
from app.main import app

def test_registration_and_login():
    print("=== Testing Public Registration and Login ===")
    
    test_email = f"test_{secrets.token_hex(4)}@gmail.com"
    with TestClient(app) as client:
        # Create a user with a non-company email
        reg_payload = {
            "email": test_email,
            "full_name": "Sai Prasad",
            "password": "Password123!",
            "role": "auditor"
        }
        
        print(f"\n1. Registering user '{test_email}' (non-company email)...")
        res = client.post("/api/v1/auth/register", json=reg_payload)
        if res.status_code == 201:
            print("[OK] User registered successfully")
            print(res.json())
        else:
            print(f"[FAIL] Registration failed: {res.status_code} - {res.text}")
            return False

        # Attempt to log in
        login_payload = {
            "email": test_email,
            "password": "Password123!"
        }
        
        print(f"\n2. Logging in with '{test_email}'...")
        res = client.post("/api/v1/auth/login", json=login_payload)
        if res.status_code == 200:
            print("[OK] Login successful!")
            tokens = res.json()
            print(tokens)
            token = tokens.get("access_token")
        else:
            print(f"[FAIL] Login failed: {res.status_code} - {res.text}")
            return False

        # Access /me
        headers = {"Authorization": f"Bearer {token}"}
        print("\n3. Verifying /me profile access...")
        res = client.get("/api/v1/auth/me", headers=headers)
        if res.status_code == 200:
            print("[OK] Profile retrieved successfully!")
            print(res.json())
            return True
        else:
            print(f"[FAIL] Profile retrieval failed: {res.status_code} - {res.text}")
            return False

if __name__ == "__main__":
    success = test_registration_and_login()
    if not success:
        sys.exit(1)
