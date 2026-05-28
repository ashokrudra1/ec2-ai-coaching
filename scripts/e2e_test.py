#!/usr/bin/env python3
"""
End-to-End Integration Test for Veda AI Coaching Platform
Tests: Groq LLM, Database, Strava OAuth, API endpoints, Telegram webhook
Run: python scripts/e2e_test.py
"""
import os
import sys
import time
import json
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8001")
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "AdminVedaSuperSecretMasterKey_2026")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []

def test(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, passed))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================================
# TEST 1: GROQ API CONNECTIVITY
# ============================================================================
section("1. GROQ LLM CONNECTIVITY")

try:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    model_large = os.getenv("GROQ_MODEL_LARGE", "llama-3.3-70b-versatile")

    test("OPENAI_API_KEY is set", bool(api_key))
    test("OPENAI_BASE_URL is set", bool(base_url), base_url or "MISSING")

    if api_key and base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)

        # Test standard model
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5, temperature=0
        )
        test(f"Standard model ({model})", bool(resp.choices[0].message.content))

        # Test large model
        resp2 = client.chat.completions.create(
            model=model_large,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5, temperature=0
        )
        test(f"Large model ({model_large})", bool(resp2.choices[0].message.content))

        # Test Groq native client
        from groq import Groq
        groq_key = os.getenv("GROQ_API_KEY") or api_key
        gc = Groq(api_key=groq_key)
        resp3 = gc.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5, temperature=0
        )
        test("Groq native client", bool(resp3.choices[0].message.content))
    else:
        test("Groq API calls", False, "Missing API key or base URL")
except Exception as e:
    test("Groq LLM overall", False, str(e)[:80])


# ============================================================================
# TEST 2: DATABASE CONNECTIVITY
# ============================================================================
section("2. DATABASE CONNECTIVITY")

try:
    from sqlalchemy import create_engine, text
    db_url = os.getenv("DATABASE_URL")
    test("DATABASE_URL is set", bool(db_url))

    if db_url:
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            test("PostgreSQL connection", result == 1)

            # Check if users table exists
            tables = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )).fetchall()
            table_names = [t[0] for t in tables]
            test("Users table exists", "users" in table_names, f"Found {len(table_names)} tables")
            test("Activities table exists", "activities" in table_names)
            test("Strava tokens table exists", "strava_tokens" in table_names or "stravatokens" in table_names or any("strava" in t and "token" in t for t in table_names))
        engine.dispose()
except Exception as e:
    test("Database overall", False, str(e)[:80])


# ============================================================================
# TEST 3: REDIS CONNECTIVITY
# ============================================================================
section("3. REDIS CONNECTIVITY")

try:
    import redis as redis_lib
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    test("REDIS_URL is set", bool(redis_url), redis_url)

    r = redis_lib.Redis.from_url(redis_url, socket_timeout=3)
    pong = r.ping()
    test("Redis PING", pong)
except Exception as e:
    test("Redis connectivity", False, str(e)[:80])


# ============================================================================
# TEST 4: API ENDPOINTS (requires running server)
# ============================================================================
section("4. API ENDPOINTS")

try:
    with httpx.Client(timeout=10.0) as http:
        # Health check
        try:
            resp = http.get(f"{BASE_URL}/health")
            test("/health endpoint", resp.status_code == 200, f"status={resp.status_code}")
            if resp.status_code == 200:
                health = resp.json()
                test("  postgres healthy", health.get("components", {}).get("postgres", {}).get("status") == "healthy")
                test("  redis healthy", health.get("components", {}).get("redis", {}).get("status") == "healthy")
                test("  openai healthy", health.get("components", {}).get("openai", {}).get("status") == "healthy")
        except httpx.ConnectError:
            test("/health endpoint", False, f"Cannot connect to {BASE_URL} — is the server running?")

        # Ping
        try:
            resp = http.get(f"{BASE_URL}/ping")
            test("/ping endpoint", resp.status_code == 200)
        except httpx.ConnectError:
            test("/ping endpoint", False, "Server not running")

        # Stats API
        try:
            resp = http.get(f"{BASE_URL}/api/stats")
            test("/api/stats endpoint", resp.status_code == 200)
        except httpx.ConnectError:
            test("/api/stats endpoint", False, "Server not running")

        # Activities API
        try:
            resp = http.get(f"{BASE_URL}/api/activities")
            test("/api/activities endpoint", resp.status_code == 200)
        except httpx.ConnectError:
            test("/api/activities endpoint", False, "Server not running")

except Exception as e:
    test("API endpoints overall", False, str(e)[:80])


# ============================================================================
# TEST 5: STRAVA OAUTH CONFIG
# ============================================================================
section("5. STRAVA OAUTH CONFIGURATION")

strava_client_id = os.getenv("STRAVA_CLIENT_ID")
strava_client_secret = os.getenv("STRAVA_CLIENT_SECRET")
strava_redirect_uri = os.getenv("STRAVA_REDIRECT_URI")

test("STRAVA_CLIENT_ID set", bool(strava_client_id), strava_client_id or "MISSING")
test("STRAVA_CLIENT_SECRET set", bool(strava_client_secret))
test("STRAVA_REDIRECT_URI set", bool(strava_redirect_uri), strava_redirect_uri or "MISSING")

if strava_redirect_uri:
    test("Redirect URI uses HTTPS", strava_redirect_uri.startswith("https://"), strava_redirect_uri)


# ============================================================================
# TEST 6: TELEGRAM BOT CONFIG
# ============================================================================
section("6. TELEGRAM BOT CONFIGURATION")

telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_secret = os.getenv("TELEGRAM_SECRET_TOKEN")

test("TELEGRAM_BOT_TOKEN set", bool(telegram_token))
test("TELEGRAM_SECRET_TOKEN set", bool(telegram_secret))

if telegram_token:
    try:
        with httpx.Client(timeout=5.0) as http:
            resp = http.get(f"https://api.telegram.org/bot{telegram_token}/getMe")
            if resp.status_code == 200:
                bot_info = resp.json()
                bot_name = bot_info.get("result", {}).get("username", "unknown")
                test("Telegram Bot API reachable", True, f"@{bot_name}")
            else:
                test("Telegram Bot API reachable", False, f"HTTP {resp.status_code}")
    except Exception as e:
        test("Telegram Bot API reachable", False, str(e)[:50])


# ============================================================================
# TEST 7: ENCRYPTION KEYS
# ============================================================================
section("7. SECURITY CONFIGURATION")

test("FIELD_ENCRYPTION_KEY set", bool(os.getenv("FIELD_ENCRYPTION_KEY")))
test("STRAVA_BYOK_SECRET_KEY set", bool(os.getenv("STRAVA_BYOK_SECRET_KEY")))
test("ADMIN_API_KEY set", bool(os.getenv("ADMIN_API_KEY")))


# ============================================================================
# TEST 8: LLM SERVICE INTEGRATION (full coaching path)
# ============================================================================
section("8. COACHING LLM INTEGRATION")

try:
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))

    from backend.llm_fallback_service import llm_router
    response = llm_router.generate_completion(
        system_instruction="You are an elite running coach. Reply in exactly 1 sentence.",
        prompt="My CTL is 45 and TSB is -8. What should I do today?",
        temperature=0.3
    )
    test("llm_router.generate_completion", bool(response) and len(response) > 10, f"{len(response)} chars")
except Exception as e:
    test("llm_router.generate_completion", False, str(e)[:100])

try:
    from backend.llm_service import generate_coach_response
    context = {
        "athlete_name": "Test User",
        "performance": "5km PB: 22:00",
        "recent_form": "3 runs this week",
        "personal_bests": "5K: 22:00, 10K: 47:00",
        "fatigue": "Moderate",
        "fatigue_trend": "Stable",
        "goal": "Sub-20 5K",
        "history": "",
        "user_input": "How should I train today?"
    }
    response = generate_coach_response(context)
    test("generate_coach_response (Groq native)", bool(response) and len(response) > 10, f"{len(response)} chars")
except Exception as e:
    test("generate_coach_response (Groq native)", False, str(e)[:100])


# ============================================================================
# SUMMARY
# ============================================================================
section("RESULTS SUMMARY")

total = len(results)
passed = sum(1 for _, p in results if p)
failed = total - passed

print(f"\n  Total: {total} | Passed: {passed} | Failed: {failed}")
print(f"  Score: {passed}/{total} ({100*passed//total}%)")

if failed == 0:
    print(f"\n  🎉 ALL TESTS PASSED — Ready for EC2 deployment!")
else:
    print(f"\n  {WARN} {failed} test(s) failed. Fix issues before deploying.")
    print(f"\n  Failed tests:")
    for name, p in results:
        if not p:
            print(f"    {FAIL} {name}")

print()
sys.exit(0 if failed == 0 else 1)
