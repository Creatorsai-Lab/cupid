from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging_config import setup_logging
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.routers.agents import router as agents_router
from app.routers.trends import router as trends_router
from app.trends.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logging system
    log_level = "DEBUG" if settings.debug else "INFO"
    setup_logging(level=log_level)
    
    import logging
    logger = logging.getLogger("app.main")
    logger.info(f"↺ Cupid API Starting - Environment: {settings.app_env}")
    logger.info(f"☱ Log Level: {log_level}")
    logger.info(f"(i) Debug Mode: {settings.debug}")
    logger.info("-" * 20)
    
    # Trends ingestion scheduler — only runs in dev.
    # In production, Celery Beat handles this instead (see scheduler.py docstring).
    if settings.app_env != "production":
        start_scheduler()

    yield

    if settings.app_env != "production":
        await stop_scheduler()
    
    logger.info("=" * 20)
    logger.info("⊘ Cupid API Shutting Down")
    logger.info("=" * 20)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cupid API",
        description="Multi-agent social media automation system",
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,    # Required for cookies to work cross-origin
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(agents_router)
    app.include_router(trends_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
