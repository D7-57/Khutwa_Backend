"""
conftest.py — shared test fixtures for Khutwa backend tests.

Sets up fake environment variables BEFORE any app module is imported,
uses an in-memory SQLite database so tests never touch a real DB, and
provides a FastAPI TestClient with auth + DB overrides already applied.
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, types
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import sessionmaker

# ── 1. Patch env vars before any app import ───────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_khutwa.db")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

# ── 1b. Make PostgreSQL JSONB compile as TEXT in SQLite ───────────────────────
#
# The production models use PostgreSQL JSONB columns.  SQLite's type system
# has no JSONB, so we register a dialect-level override that renders it as
# TEXT.  This is only used when creating/using the test tables; it has no
# effect on the production database.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

if not hasattr(SQLiteTypeCompiler, "_orig_visit_JSONB"):
    def _sqlite_visit_JSONB(self, type_, **kw):  # noqa: N802
        return "TEXT"

    SQLiteTypeCompiler._orig_visit_JSONB = SQLiteTypeCompiler.visit_JSONB if hasattr(SQLiteTypeCompiler, "visit_JSONB") else None  # type: ignore[attr-defined]
    SQLiteTypeCompiler.visit_JSONB = _sqlite_visit_JSONB  # type: ignore[attr-defined]

# Add the project root to sys.path so `app.*` imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.base import Base                        # noqa: E402  (must be after env patch)
from app.db.session import get_db                   # noqa: E402
from app.core.security import (                     # noqa: E402
    get_current_user_id,
    get_current_auth_user,
    AuthUser,
)
from app.main import app                            # noqa: E402


# ── 2. In-memory SQLite engine for tests ─────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite://"  # pure in-memory; no file created

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    # StaticPool ensures every call to engine.connect() returns the SAME
    # underlying connection, which means all sessions see the same in-memory DB.
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all ORM tables once per test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Yield a fresh DB session for each test, rolled back afterwards."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── 3. Test user ──────────────────────────────────────────────────────────────

TEST_USER_ID = str(uuid.uuid4())


# ── 4. FastAPI TestClient with dependency overrides ───────────────────────────

@pytest.fixture()
def client(db):
    """
    TestClient with three overrides:
      • get_db               → in-memory SQLite session (no real Postgres needed)
      • get_current_user_id  → TEST_USER_ID (no real JWT validation)
      • get_current_auth_user → mock AuthUser (no real JWT validation)
    """
    def _override_get_db():
        yield db

    def _override_get_user_id():
        return TEST_USER_ID

    def _override_get_auth_user():
        return AuthUser(id=TEST_USER_ID, email="test@khutwa.test")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user_id] = _override_get_user_id
    app.dependency_overrides[get_current_auth_user] = _override_get_auth_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def client_unauth():
    """TestClient with only the DB override — no auth (tests 401 behaviour)."""
    def _override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
