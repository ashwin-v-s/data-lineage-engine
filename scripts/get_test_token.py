"""
scripts/get_test_token.py
──────────────────────────
Sign up (or sign in) a dedicated test account on the shared Supabase project
and print the KAIROS_TEST_USER_TOKEN value so it can be added to .env.

Usage:
    python scripts/get_test_token.py

The script:
  1. Tries to SIGN IN first (in case the account already exists).
  2. If sign-in fails, attempts to SIGN UP and create the account.
  3. Prints the access_token on success.
  4. If signup requires email confirmation, prints instructions.

Never commits credentials. Token is printed to stdout only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from repo root
root = Path(__file__).resolve().parent.parent
env_file = root / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=False)

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

TEST_EMAIL = "pranavsamal43@gmail.com"   # your GitHub email — change if different
TEST_PASSWORD = "Kairos_Test_2026!"

if not SUPABASE_URL or not ANON_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY not set in .env")
    sys.exit(1)

headers = {
    "apikey": ANON_KEY,
    "Content-Type": "application/json",
}


def sign_in() -> dict | None:
    """Try to sign in with existing credentials."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    resp = httpx.post(
        url,
        headers=headers,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def sign_up() -> dict | None:
    """Try to sign up a new account."""
    url = f"{SUPABASE_URL}/auth/v1/signup"
    resp = httpx.post(
        url,
        headers=headers,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    if resp.status_code in (200, 201):
        return resp.json()
    print(f"Signup failed: {resp.status_code} {resp.text}")
    return None


def main() -> None:
    print(f"Supabase URL : {SUPABASE_URL}")
    print(f"Test email   : {TEST_EMAIL}")
    print()

    # Step 1: Try sign in (account may already exist)
    print("Step 1: Trying sign-in...")
    data = sign_in()
    if data and data.get("access_token"):
        token = data["access_token"]
        print(f"\n✅ Signed in successfully!")
        print(f"\nKAIROS_TEST_USER_TOKEN={token}")
        print("\nAdd that line to your .env file.")
        return

    # Step 2: Try sign up
    print("Sign-in failed (account may not exist yet). Trying sign-up...")
    data = sign_up()
    if not data:
        print("\nERROR: Sign-up also failed. Check SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.")
        sys.exit(1)

    # Check if email confirmation is required
    user = data.get("user") or data
    email_confirmed = user.get("email_confirmed_at") or user.get("confirmed_at")
    access_token = data.get("access_token")

    if access_token:
        print(f"\n✅ Signed up and got token immediately (email confirmation not required).")
        print(f"\nKAIROS_TEST_USER_TOKEN={access_token}")
        print("\nAdd that line to your .env file.")
        return

    if not email_confirmed:
        print(f"\n📧 Sign-up succeeded but EMAIL CONFIRMATION IS REQUIRED.")
        print(f"\nWhat to do:")
        print(f"  1. Check the inbox for: {TEST_EMAIL}")
        print(f"     (This is a Gmail — you need to create this account or use your own email below)")
        print(f"  2. Click the confirmation link in the email.")
        print(f"  3. Then re-run this script — it will sign in and print the token.")
        print(f"\nOR — change TEST_EMAIL in this script to your own email and re-run.")
        return

    print(f"\nUnexpected response: {data}")


if __name__ == "__main__":
    main()
