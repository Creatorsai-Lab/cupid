from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.db import async_session
from app.core.logging_config import setup_logging
from app.earn.router import router as earn_router
from app.earn.scheduler import run_earn_scheduler
from app.insights.scheduler import start_scheduler as start_insights_scheduler
from app.insights.scheduler import stop_scheduler as stop_insights_scheduler
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.connections import router as connections_router
from app.routers.history_router import router as history_router
from app.routers.insights_router import router as insights_router
from app.routers.profile import router as profile_router
from app.routers.trends import router as trends_router
from app.trends.scheduler import start_scheduler as start_trends_scheduler
from app.trends.scheduler import stop_scheduler as stop_trends_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logging system
    log_level = "DEBUG" if settings.debug else "INFO"
    setup_logging(level=log_level)

    import asyncio
    import logging

    logger = logging.getLogger("app.main")
    logger.info(f"↺ Cupid API Starting - Environment: {settings.app_env}")
    logger.info(f"☱ Log Level: {log_level}")
    logger.info(f"(i) Debug Mode: {settings.debug}")
    logger.info("-" * 20)

    try:
        from app.core.redis import redis_client

        await redis_client.ping()
        logger.info("✓ Redis connection verified")
    except Exception as exc:
        logger.error("✗ Redis unreachable at startup: %s", exc)

    # schedulers - only runs in dev.
    # In production, Celery Beat handles this instead (see scheduler.py docstring).
    earn_task = None
    if settings.app_env != "production":
        start_trends_scheduler()
        start_insights_scheduler()
        earn_task = asyncio.create_task(run_earn_scheduler(async_session))

    yield

    if settings.app_env != "production":
        await stop_trends_scheduler()
        await stop_insights_scheduler()
        if earn_task is not None:
            earn_task.cancel()

    logger.info("⊘ Cupid API Shutting Down")
    logger.info("-" * 20)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cupid API",
        description="Multi-agent content creation platform",
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(agents_router)
    app.include_router(trends_router, prefix="/api/v1")
    app.include_router(connections_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(earn_router)

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
