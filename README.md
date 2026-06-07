# Cupid

A multi-agent social media automation system that learns your voice, tracks what is trending in your domain, and composes publication-ready posts that sound authentically like you.

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

All agent state is typed via `MemoryState`. No agent holds internal state between runs. All persistence is in PostgreSQL and ChromaDB.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Python 3.11 |
| Agent Orchestration | LangGraph |
| Database | PostgreSQL 16 (via SQLAlchemy + Alembic) |
| Vector Store | ChromaDB |
| Task Queue | Celery + Redis |
| LLM Runtime | Ollama (local) |
| Embeddings | nomic-embed-text via Ollama |
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui |
| State Management | Zustand, TanStack Query |

---

## Prerequisites

Before running Cupid locally, ensure the following are installed:

- Python 3.11 or higher
- Node.js 18 or higher and npm
- Docker Desktop (running)
- Ollama — [ollama.com](https://ollama.com)
- Git

---

## Local Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/your-username/cupid.git
cd cupid
```

### 2. Start Infrastructure Services

From the project root, start PostgreSQL, Redis, and ChromaDB via Docker:

```powershell
docker compose up -d
```

Verify all containers are healthy:

```powershell
docker compose ps
```

You should see `cupid_postgres`, `cupid_redis`, and `cupid_chroma` all in a running state.

### 3. Pull Ollama Models

Cupid uses local LLMs via Ollama. Pull the required models:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 4. Backend Setup

Navigate to the backend directory:

```powershell
cd backend
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run this once and retry:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Install dependencies:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Configure environment variables. Copy the example file and fill in your values:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and set at minimum:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db
REDIS_URL=redis://localhost:6379/0
```

Run database migrations:

```powershell
alembic upgrade head
```

Start the API server:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Verify the backend is live:

```
http://localhost:8000/health         → {"status": "ok", "env": "development"}
http://localhost:8000/api/docs       → Swagger UI (interactive API docs)
```

### 5. Frontend Setup

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
| Ollama | `ollama serve` | Terminal 1 |
| Backend API | `python -m uvicorn app.main:app --reload --port 8000` | Terminal 2 |
| Celery Worker | `celery -A app.celery_app worker --loglevel=info` | Terminal 3 |
| Frontend | `npm run dev` | Terminal 4 |

---

## Project Structure

```
cupid/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory
│   │   ├── config.py             # Pydantic settings
│   │   ├── agents/               # LangGraph agent nodes
│   │   ├── services/             # Non-agent algorithm services
│   │   │   ├── analytics.py
│   │   │   ├── scheduler.py
│   │   │   ├── brand_safety.py
│   │   │   └── notifications.py
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── models/               # SQLAlchemy ORM models
│   │   └── core/                 # DB, Redis, ChromaDB clients
│   ├── alembic/                  # Migration files
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/                      # Next.js App Router
│   ├── components/
│   └── lib/
├── docs/                         # Architecture docs, ADRs
├── scripts/                      # Dev utilities, seed scripts
├── docker-compose.yml
└── README.md
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing key. Use a long random string in production. |
| `DATABASE_URL` | Yes | PostgreSQL async connection string. |
| `REDIS_URL` | Yes | Redis connection string. |
| `CHROMA_HOST` | Yes | ChromaDB host (default: localhost). |
| `CHROMA_PORT` | Yes | ChromaDB port (default: 8001). |
| `OLLAMA_BASE_URL` | Yes | Ollama server URL (default: http://localhost:11434). |
| `OLLAMA_LLM_MODEL` | Yes | LLM model name pulled via Ollama. |
| `OLLAMA_EMBED_MODEL` | Yes | Embedding model name pulled via Ollama. |
| `TAVILY_API_KEY` | No | Optional. Enriches Research Agent search. Free tier available. |
| `REDDIT_CLIENT_ID` | No | Optional. Enables Reddit trend source. |
| `RESEND_API_KEY` | No | Optional. Enables email notifications. |

---

## Code Quality & Tooling

Cupid enforces consistent style and catches mistakes automatically at three
layers: **as you save** (EditorConfig), **before you commit** (pre-commit
hooks), and **before you merge** (GitHub Actions CI).

| Layer | Backend (Python) | Frontend (TypeScript/React) |
|---|---|---|
| Linter | **Ruff** (`E,F,I,N,W,UP`) | **ESLint** (Next config) |
| Formatter | **Ruff format** | **Prettier** (+ Tailwind class sorting) |
| Types | — | **TypeScript** (`tsc --noEmit`) |
| Editor baseline | `.editorconfig` | `.editorconfig` |
| Pre-commit | `pre-commit` framework | `pre-commit` framework |
| CI gate | GitHub Actions | GitHub Actions |

### One-time setup

```powershell
# 1. Frontend: install Prettier + ESLint deps
cd frontend
npm install

# 2. Pre-commit hooks (from the repo root, in your Python env)
cd ..
pip install pre-commit
pre-commit install        # wires the hooks into .git so they run on every commit
```

### Frontend commands (run inside `frontend/`)

| Command | What it does | Expect |
|---|---|---|
| `npm run format` | Prettier rewrites all files to the canonical style (and sorts Tailwind classes). | Files get reformatted in place. The **first run touches many files** — commit that as one "format" commit. |
| `npm run format:check` | Checks formatting **without** writing. Used by CI. | Exit 0 if clean; lists files + non-zero exit if not. |
| `npm run lint` | ESLint finds bugs/anti-patterns. | Prints warnings/errors; non-zero exit on error. |
| `npm run lint:fix` | ESLint auto-fixes what it safely can. | Fixable issues disappear; the rest are reported. |
| `npm run typecheck` | `tsc --noEmit` — full TypeScript type check, no output files. | Exit 0 if types are sound; lists type errors otherwise. |

### Backend commands (run inside `backend/`, venv active)

| Command | What it does | Expect |
|---|---|---|
| `ruff check .` | Lints all Python (imports, unused vars, naming, pyupgrade…). | Lists violations; non-zero exit if any. |
| `ruff check . --fix` | Lints **and** auto-fixes the safe ones. | Fixable issues vanish; rest reported. |
| `ruff format .` | Formats all Python (Black-compatible). | Files reformatted in place. |
| `ruff format --check .` | Format check only (no writes). Used by CI. | Exit 0 if clean, non-zero otherwise. |

### Pre-commit (runs automatically on `git commit`)

After `pre-commit install`, every commit runs the hooks **on your staged files only**:

- Ruff lint + format on changed `backend/**` Python
- Hygiene: trailing whitespace, final newline, merge-conflict markers, YAML/JSON validity, large-file guard

Frontend formatting is **not** in pre-commit (Node formatters with local plugins
don't resolve reliably inside pre-commit's isolated env on Windows). It's enforced
by your editor's "format on save" and by CI (`npm run format:check`).

If a hook reformats a file, the commit is **aborted** and the fixes are left
staged-but-unstaged — review them, `git add`, and commit again. To run every
hook against the whole repo manually:

```powershell
pre-commit run --all-files
```

To bypass hooks in an emergency (avoid this): `git commit --no-verify`.

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
.venv\Scripts\Activate.ps1
pytest
```

Run with coverage:

```powershell
pytest --cov=app --cov-report=term-missing
```

---

## API Documentation

When the backend is running in development mode, full interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

---

## License

MIT License. See [LICENSE](./LICENSE) for full terms.
