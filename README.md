# Cupid

A multi-agent social media automation system that learns your voice, tracks what is trending in your domain, and composes publication-ready posts that sound authentically like you.

---

## What It Does

Cupid orchestrates four specialized AI agents through a shared state pipeline:

- **Persona Agent** — Builds and maintains a living model of your voice, tone, vocabulary, and domain expertise using RAG over your writing samples.
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
    ├── Persona Agent          → retrieves user identity context
    ├── Research Agent         → finds angles, sources, ideas
    ├── Trend Intelligence Agent → trending topics, hashtags, timing
    └── Composer Agent         → assembles platform-specific post
    │
    ▼
Structured Output → FastAPI → Next.js Frontend
```

All agent state is typed via `CupidState`. No agent holds internal state between runs. All persistence is in PostgreSQL and ChromaDB.

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
│   │   │   ├── state.py          # CupidState TypedDict
│   │   │   ├── graph.py          # StateGraph assembly
│   │   │   ├── persona.py
│   │   │   ├── research.py
│   │   │   ├── trend.py
│   │   │   └── composer.py
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