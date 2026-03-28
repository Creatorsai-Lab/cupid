"""
Database engine and session management.
Key concepts:
- Engine: maintains a CONNECTION POOL to PostgreSQL (doesn't open a new
  connection per request — that would be slow and wasteful)
- AsyncSession: a single "conversation" with the database. Each API request
  gets its own session via the `get_db` dependency.
- The `async for` pattern ensures sessions are always closed, even if
  the request handler throws an error (like a try/finally).
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

# The engine manages a pool of database connections.
# echo=False in production — set True temporarily to see raw SQL in logs.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,  # keep 5 connections open at all times
    max_overflow=10,  # allow up to 10 more under load
    pool_pre_ping=True,   # test connections before using (handles DB restarts)
)

# Session factory — creates new sessions from the engine.
# expire_on_commit=False means objects stay usable after commit
# (default True would require re-querying after every commit).
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Dependency for FastAPI: yields one session per request.
# The `async for` ensures session.close() is called automatically.
async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency that provides a database session per request.
    
    Usage in a router:
        @router.post("/something")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    
    The `yield` makes this a generator — FastAPI calls __anext__ to get
    the session, then __anext__ again after the response to close it.
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()