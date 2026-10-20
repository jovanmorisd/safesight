"""Tests never touch the real Supabase project configured in backend/.env.

Empty values set here win over .env (python-dotenv does not override existing variables), so the
app falls back to a throwaway SQLite database and local image folder. To run the suite against a
Postgres on purpose, set TEST_DATABASE_URL.
"""
import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ALLOW_SIGNUP"] = "true"
