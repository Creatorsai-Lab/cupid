"""
Conftest: The brain. Defines all the fixtures - reusable setup that any test can pull in by name. This is the magic file.

Test Infrastructure — shared fixtures for all tests.

WHAT THIS FILE DOES
-------------------
Pytest auto-discovers any file named `conftest.py` and makes its fixtures
available to every test in the same directory tree. Tests pull what they
need by listing fixture names as parameters — pytest wires them up.

For example, a test that needs a database session writes:

    async def test_something(db_session):
        result = await db_session.execute(...)

Pytest sees `db_session` in the parameter list, calls our fixture below,
and passes the result. After the test finishes, the fixture's cleanup
code runs automatically.

DESIGN DECISIONS
----------------

1. SEPARATE TEST DATABASE
   Tests must NEVER write to your real cupid_db. We create a dedicated
   `cupid_test_db` that gets truncated between tests. Same Postgres
   instance, different database — fast and isolated.

2. SESSION-SCOPED ENGINE, FUNCTION-SCOPED SESSION
   Creating an engine is expensive (~100ms). Creating a session is cheap.
   We make the engine once per pytest run (`scope="session"`) and a fresh
   session per test (default `scope="function"`). This is the standard
   pattern.

3. ROLLBACK-BASED ISOLATION
   Each test runs inside a transaction. After the test, we ROLLBACK —
   nothing persists. Tests stay independent without slow truncates.

4. ASYNC ALL THE WAY
   Your app is async-first. Tests must be too. We use httpx.AsyncClient
   instead of TestClient (which is sync) so async code paths get exercised.

PRODUCTION CI NOTES
------------------
When you set up GitHub Actions later, these fixtures work the same way.
The CI just needs:
    - Postgres service running (docker-compose or GitHub services block)
    - Environment variable TEST_DATABASE_URL pointing at the test DB
The conftest doesn't change — the environment provides the DB URL.
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import your application bits
from app.models.user import Base
from app.main import app


# ─── Test database URL ─────────────────────────────────────────
# Override via env var for CI; default to a dev-friendly local DB.
# Note: this is a SEPARATE database from your dev one — `cupid_test_db`.
# Make sure it exists. (Setup instructions in the README of this folder.)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_test_db",
)


# ─── Event loop fixture ────────────────────────────────────────
# pytest-asyncio creates a new event loop per test by default. For shared
# fixtures (like the engine), we want one loop for the whole session.

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop so async fixtures can be session-scoped too."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── Database engine (session-scoped) ──────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    One engine for the entire test session.

    Why session-scoped: creating an engine is expensive (connection pool
    setup, dialect inspection). Tests just borrow connections from the
    engine — they don't need their own.
    """
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables once at session start
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    # Drop all tables at session end (clean slate next run)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


# ─── Database session (function-scoped, with rollback isolation) ──

@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    A fresh DB session per test. All writes are rolled back at the end,
    so tests never see each other's data.

    Pattern: connection → transaction → session.
    The session is bound to the connection; the transaction is on the
    connection. When we rollback, everything done in this test vanishes.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()

        Session = async_sessionmaker(
            bind=connection, expire_on_commit=False, class_=AsyncSession,
        )

        async with Session() as session:
            yield session

        # Rollback — nothing this test wrote actually persists
        await transaction.rollback()


# ─── HTTP test client ──────────────────────────────────────────

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    An anonymous async HTTP client targeting your FastAPI app.

    No real network — httpx talks to the ASGI app directly via
    ASGITransport. Faster than launching uvicorn, identical behavior.

    Use this for testing endpoints that don't require auth.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Sample data fixtures ──────────────────────────────────────
# These are the "Lego blocks" tests use to build scenarios. Define
# common shapes once, reuse everywhere.

@pytest.fixture
def sample_persona() -> dict:
    """A minimal persona dict — the shape the ranker expects."""
    return {
        "name": "Test User",
        "content_niche": "ai/ml",
        "target_audience": "developers and researchers",
        "bio": "I write about machine learning and software engineering.",
        "usp": "deep technical clarity for self-taught engineers",
    }


@pytest.fixture
def sample_persona_empty() -> dict:
    """An empty persona — tests the ranker's behavior on cold-start users."""
    return {}