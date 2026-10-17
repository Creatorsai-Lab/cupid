"""Shared test fixtures. See tests/tests.md for how the suite is organized.

Only fixtures used across features live here; a feature's own fixtures go in
that feature's conftest.py (e.g. tests/trends/conftest.py).

Database tests run against a separate Postgres database (`cupid_test_db`, or
TEST_DATABASE_URL). Tables are created once per run from the models; each test
runs inside a transaction that is rolled back, so tests never see each other's
data and code under test may still call `commit()`.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.core.tables import metadata
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_test_db",
)


DB_FIXTURES = {"engine", "db_session"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test that uses the database as `db`, so it can't be forgotten."""
    for item in items:
        if DB_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """psycopg (Postgres checkpoints) can't use Windows' default Proactor loop."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    """Overrides set by one test (signed-in user, DB session) never leak into the next."""
    yield
    app.dependency_overrides.clear()


# ── Database ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    """One engine and a fresh schema per test run.

    Locally, DB tests are skipped with a hint if Postgres isn't running;
    in CI (CI is set) an unreachable database fails the run instead.
    """
    eng = create_async_engine(TEST_DATABASE_URL)
    try:
        async with eng.begin() as conn:
            await conn.run_sync(metadata.drop_all)  # clean slate after a crashed run
            await conn.run_sync(metadata.create_all)
    except (OSError, DBAPIError) as exc:
        await eng.dispose()
        if os.environ.get("CI"):
            raise
        pytest.skip(
            f"Postgres test DB unreachable ({type(exc).__name__}); "
            "run: docker compose up -d"
        )

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test.

    join_transaction_mode="create_savepoint" turns the code's own commit() calls
    into savepoints, so the outer rollback still undoes everything.
    """
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


# ── HTTP ───────────────────────────────────────────────────────


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """HTTP client talking to the app in-process (no server, no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def db_client(client: AsyncClient, db_session: AsyncSession) -> AsyncClient:
    """`client` whose requests use the test database session."""

    async def _test_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _test_db
    return client


@pytest.fixture
def sign_in() -> Callable[[User], User]:
    """Make requests act as `user`: `sign_in(user)` skips the cookie check."""

    def _sign_in(user: User) -> User:
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _sign_in
