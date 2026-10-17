# Cupid

A multi-agent social media automation system that learns your voice, tracks what is trending in your domain, and composes publication-ready posts that sound authentically like you.

> _by_ Adya Prasad

---

## What It Does

Cupid orchestrates four specialized AI agents through a shared state pipeline:

- ** Agent** — Builds and maintains a living model of your voice, tone, vocabulary, and domain expertise using RAG over your writing samples.
- **Research & Ideation Agent** — Given your persona and a topic signal, autonomously researches and returns structured post angle ideas with supporting evidence.
- **Trend Intelligence Agent** — Monitors Reddit, HackerNews, and RSS feeds in your domain. Scores trending topics by velocity and filters them against your persona.
- **Composer Agent** — Takes all upstream context and produces platform-specific, publication-ready posts with a persona fidelity check before output.

Analytics, scheduling, brand safety, and notifications are handled by deterministic algorithm-based services — not additional LLM agents.

---

## Architecture Overview

```
User Intent
    │
    ▼
Orchestrator (LangGraph StateGraph)
    │
    ├── Personalization Agent   → retrieves user identity context
    ├── Research Agent         → finds angles, sources, ideas
    └── Composer Agent         → assembles platform-specific post
    │
    ▼
Structured Output → FastAPI → Next.js Frontend
```

All agent state is typed via `MemoryState`. No agent holds internal state between runs. All persistence is in PostgreSQL.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Python 3.12 (managed with uv) |
| Agent Orchestration | LangGraph |
| Database | PostgreSQL 16 (via SQLAlchemy + Alembic) |
| Cache | Redis |
| LLM Providers | Groq (free tier) |
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui |
| State Management | Zustand, TanStack Query |

---

## Prerequisites

Before running Cupid locally, ensure the following are installed:

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you)
- Node.js 18 or higher and npm
- Docker Desktop (running)
- Git

---

## Local Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/your-username/cupid.git
cd cupid
```

### 2. Start Infrastructure Services

From the project root, start PostgreSQL and Redis via Docker:

```powershell
docker compose up -d
```

Verify all containers are healthy:

```powershell
docker compose ps
```

You should see `cupid_postgres` and `cupid_redis` in a running state.

### 3. Backend Setup

Navigate to the backend directory:

```powershell
cd backend
```

Install dependencies with [uv](https://docs.astral.sh/uv/). This creates `.venv` from
`pyproject.toml` and `uv.lock`; there is no venv to activate — prefix commands with `uv run`:

```powershell
uv sync
```

Configure environment variables. Copy the example file and fill in your values:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and set at minimum:

```env
SECRET_KEY=your-secret-key-here
database_url=postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db
REDIS_URL=redis://localhost:6379/0
```

Run database migrations:

```powershell
uv run alembic upgrade head
```

Start the API server:

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

On Windows, keep `--reload` (or pass `--loop asyncio:SelectorEventLoop`): the agent run
queue uses psycopg, which can't run on Windows' default event loop.

Start the agent worker (runs content pipelines; a second backend window):

```powershell
uv run saq app.agents.runtime.worker.worker_settings
```

Verify the backend is live:

```
http://localhost:8000/health         → {"status": "ok", "env": "development"}
http://localhost:8000/api/docs       → Swagger UI (interactive API docs)
```

### 4. Frontend Setup

Open a second PowerShell window:

```powershell
cd cupid\frontend
npm install
npm run dev
```

The frontend will be available at:

```
http://localhost:3000
```

---

## Running the Full System

To run the complete local stack you need four things active simultaneously:

| Process | Command | Window |
|---|---|---|
| Infrastructure | `docker compose up -d` | Background |
| Backend API | `uv run uvicorn app.main:app --reload --port 8000` | Terminal 1 |
| Agent worker | `uv run saq app.agents.runtime.worker.worker_settings` | Terminal 2 |
| Frontend | `npm run dev` | Terminal 3 |

---

## Project Structure

```
cupid/
├── backend/
│   ├── app/                      # one folder per feature: models.py · schemas.py · service.py · router.py · deps.py
│   │   ├── main.py               # FastAPI app setup: routers, error handler, startup/shutdown
│   │   ├── config.py             # Settings (pydantic-settings, reads backend/.env)
│   │   ├── core/                 # shared infrastructure: db (Base, DbSession), tables, errors, redis, logging
│   │   ├── auth/                 # Google sign-in, session cookie, current user
│   │   ├── profile/              # creator profile (personalization)
│   │   ├── connections/          # YouTube OAuth connection
│   │   ├── insights/             # YouTube analytics
│   │   ├── history/              # saved creations
│   │   ├── trends/               # trending articles
│   │   ├── earn/                 # monetization readiness
│   │   ├── subscriptions/        # plans and entitlements
│   │   ├── admin/                # admin dashboard, audit log
│   │   └── agents/               # content pipeline (being rebuilt, see dev_resources/updated_version_plan.md)
│   ├── tests/                    # mirrors app/: tests/<feature>/
│   ├── scripts/                  # one-off maintenance scripts
│   ├── alembic/                  # database migrations
│   ├── pyproject.toml            # dependencies + tool config (ruff, pyright, pytest)
│   ├── uv.lock                   # exact versions (generated by uv)
│   └── .env.example
├── frontend/
│   ├── app/                      # Next.js App Router
│   ├── components/
│   └── lib/
├── dev_resources/                # plans, guides, notes
├── docker-compose.yml            # Postgres + Redis
└── README.md
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing key. Use a long random string in production. |
| `database_url` | Yes | PostgreSQL async connection string. |
| `REDIS_URL` | Yes | Redis connection string. |
| `FRONTEND_URL` | Yes | Frontend origin for CORS and redirects. |
| `TOKEN_ENCRYPTION_KEY` | Yes | Fernet key that encrypts stored OAuth tokens. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client for login and YouTube connect. |
| `GROQ_API_KEY` | Yes | LLM provider used by the agents. |
| `TAVILY_API_KEY` | Phase 3 | Web search for the new research agent. |
| `GNEWS_API_KEY` | No | News source for trends. |
| `ADMIN_*` | No | Admin allowlist and dashboard login. |

The full list, with defaults, is `backend/.env.example`.

---

## Code Quality & Tooling

Cupid checks code at two layers: **when you run the tools** (locally, from
`backend/` with `uv run`, no venv activation) and **before you merge** (GitHub Actions CI).

| Layer | Backend (Python) | Frontend (TypeScript/React) |
|---|---|---|
| Linter | **Ruff** (`E,F,I,N,W,UP`) | **ESLint** (Next config) |
| Formatter | **Ruff format** | **Prettier** (+ Tailwind class sorting) |
| Types | **Pyright** (standard mode) | **TypeScript** (`tsc --noEmit`) |
| Tests | **pytest** | **Vitest** |
| Editor baseline | `.editorconfig` | `.editorconfig` |
| CI gate | GitHub Actions | GitHub Actions |

### One-time setup

```powershell
cd backend
uv sync            # Python, all dependencies and dev tools into backend/.venv
cd ../frontend
npm install        # Prettier, ESLint, TypeScript
```

### Frontend commands (run inside `frontend/`)

| Command | What it does | Expect |
|---|---|---|
| `npm run format` | Prettier rewrites all files to the canonical style (and sorts Tailwind classes). | Files get reformatted in place. |
| `npm run format:check` | Checks formatting **without** writing. Used by CI. | Exit 0 if clean; lists files + non-zero exit if not. |
| `npm run lint` | ESLint finds bugs/anti-patterns. | Prints warnings/errors; non-zero exit on error. |
| `npm run lint:fix` | ESLint auto-fixes what it safely can. | Fixable issues disappear; the rest are reported. |
| `npm run typecheck` | `tsc --noEmit` — full TypeScript type check, no output files. | Exit 0 if types are sound; lists type errors otherwise. |

### Backend commands (run inside `backend/`)

| Command | What it does | Expect |
|---|---|---|
| `uv run ruff check .` | Lints all Python (imports, unused vars, naming, pyupgrade…). | Lists violations; non-zero exit if any. |
| `uv run ruff check . --fix` | Lints **and** auto-fixes the safe ones. | Fixable issues vanish; rest reported. |
| `uv run ruff format .` | Formats all Python (Black-compatible). | Files reformatted in place. |
| `uv run ruff format --check .` | Format check only (no writes). Used by CI. | Exit 0 if clean, non-zero otherwise. |
| `uv run pyright` | Type-checks `app/`, `tests/`, `scripts/` (config in `pyproject.toml`). | Lists type errors; non-zero exit if any. |
| `uv run pytest` | Fast offline test suite (~1 s). | Exit 0 when green. |
| `uv run pytest -m integration` | Tests that call real LLM/search APIs (needs keys). | Slower; uses API quota. |

### Continuous Integration

`.github/workflows/ci.yml` runs on every pull request and push to `main`:

- **Backend job** — `ruff check` + `ruff format --check`
- **Frontend job** — `prettier --check` → `eslint` → `tsc --noEmit` → `next build`

A failing check blocks the merge. Run the same commands locally before pushing
to get a green check on the first try.

> First-time note: running `npm run format` and `ruff format .` once across the
> existing codebase will produce a large but mechanical diff. Land it as a single
> dedicated "apply formatter" commit so future diffs stay clean and reviewable.

---

## Running Tests

```powershell
cd backend
uv run pytest
```

Run with coverage:

```powershell
uv run pytest --cov=app --cov-report=term-missing
```

---

## API Documentation

When the backend is running in development mode, full interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

---

## License

MIT License. See [LICENSE](./LICENSE) for full terms.
