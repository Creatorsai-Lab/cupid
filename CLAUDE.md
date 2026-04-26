# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cupid is a multi-agent AI content creation platform. It orchestrates three LangGraph agents (Personalization → Research → Composer) to generate platform-specific social media posts tailored to a user's voice and niche.

## Commands

### Backend (Python / FastAPI)

```bash
cd backend

# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure (run first)
docker compose up -d          # PostgreSQL 16, Redis 7, ChromaDB
ollama pull llama3.2 && ollama pull nomic-embed-text
ollama serve                  # separate terminal

# Database
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "description"  # new migration

# Run API
python -m uvicorn app.main:app --reload --port 8000

# Run Celery worker
celery -A app.celery_app worker --loglevel=info

# Tests
pytest                        # all tests
pytest tests/test_agents.py   # single file
pytest -k "test_composer"     # single test by name
pytest --cov=app --cov-report=term-missing

# Lint / format / type-check
ruff check .
ruff format .
mypy app/
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev     # dev server on port 3000
npm run build && npm start
npm run lint
```

## Architecture

### Agent Pipeline (LangGraph)

All three agents share a typed `MemoryState` (TypedDict) defined in `backend/app/agents/state.py`. The LangGraph `StateGraph` in `backend/app/agents/graph.py` wires them sequentially:

```
POST /api/v1/agents/generate
        │
[Personalization Agent]  — decomposes topic into 5 orthogonal search queries
        │
[Research Agent]         — web search + BM25/persona-ranked page extraction
        │
[Composer Agent]         — generates 3 post variants, multi-axis quality scoring
        │
JSON result stored in-memory (keyed by run_id); poll via GET /api/v1/agents/runs/{run_id}
```

**Provider fallback pattern** (used in Personalization and Composer):
1. Groq (Llama 3.3 70B) — primary
2. HuggingFace Inference API — fallback
3. Deterministic heuristic — never-fail safety net (Personalization only; Composer fails if both LLMs fail)

### Key directories

```
backend/app/
  agents/
    state.py             — MemoryState TypedDict (single source of truth for pipeline state)
    graph.py             — LangGraph StateGraph orchestrator
    personalization/     — query decomposition agent
    research/            — web search + page extraction pipeline
    composer/            — 3-variant post generation + quality scoring
  routers/               — FastAPI routes (agents, auth, profile)
  models/                — SQLAlchemy ORM models (User, UserPersonalization)
  schemas/               — Pydantic request/response schemas
  services/              — Non-agent business logic (auth, profile)
  core/                  — DB, Redis, ChromaDB async clients
  config.py              — Pydantic Settings (all env vars with defaults)
  main.py                — FastAPI app factory (lifespan, CORS, routers)

frontend/
  app/
    (auth)/              — login, register pages
    (dashboard)/         — create posts, settings
  components/            — shared React components
  lib/
    api.ts               — typed API client (agentsApi, authApi, profileApi)
    store.ts             — Zustand auth state (persisted to localStorage)
```

### Data persistence

| Store | Purpose |
|---|---|
| PostgreSQL | Users, user profiles (async via sqlalchemy-asyncpg) |
| ChromaDB | Voice/persona embeddings |
| Redis | Celery task queue |
| In-memory dict | Agent run results (MVP only — not production-safe across restarts) |

### API surface

- `POST /api/v1/agents/generate` — kick off pipeline, returns `run_id`
- `GET /api/v1/agents/runs/{run_id}` — poll for status/results
- Auth: register, login, logout, me
- Profile: get, update
- `GET /health`
- Swagger UI: `http://localhost:8000/api/docs`

## Environment Variables

Copy `backend/.env.example` to `backend/.env`. Critical vars:

```
DATABASE_URL=postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db
REDIS_URL=redis://localhost:6380/0
CHROMA_HOST=localhost
CHROMA_PORT=8001
OLLAMA_BASE_URL=http://localhost:11434
GROQ_API_KEY=...          # primary LLM provider
HUGGINGFACE_API_KEY=...   # fallback LLM provider
```

Frontend: set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

## Code Conventions

- **Async-first:** All DB and HTTP I/O uses `async`/`await`. Never add sync blocking calls in async paths.
- **State is immutable between agents:** each agent reads from and returns an updated copy of `MemoryState`; never mutate state in-place.
- **Ruff line length is 88.** MyPy is configured non-strict; `asyncio_mode="auto"` in pytest (no manual `@pytest.mark.asyncio` needed).
- **Composer generates exactly 3 variants** (hook-first, data-driven, story-led). Quality scoring is multi-axis: length fit, grounding, persona match, hook strength.