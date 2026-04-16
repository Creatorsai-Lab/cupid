from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.routers.agents import router as agents_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[cupid] Starting in {settings.app_env} mode")
    yield
    print("[cupid] Shutting down")


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

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
