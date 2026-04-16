
## 2. Architecture Philosophy

### Principles
- Use Swarm architecture agent orchestration debugging we need specialized tooling (distributed tracing, event sourcing, blackboard snapshots).
- Without an orchestrator deciding when to stop, swarm agents need explicit termination conditions , max iterations, quality thresholds, or timeout-based convergence. Design these conditions carefully; too-aggressive termination produces incomplete results, while too-conservative termination burns tokens and compute.
- At the implementation level, orchestration will involves four components: **a registry** of available agents (4 as of now) and their capabilities, a **router** that maps incoming tasks to the best agent or sequence of agents, a **state store** for shared context and conversation history, user persona, and a **supervisor system or algorith or service** that monitors timeouts, retries, and escalations.
- The hardest problem in multi-agent orchestration isn't routing , it's **state**. When a customer says "I need help with my recent order" to a triage agent, and the triage agent routes to a billing specialist, what context transfers? The full conversation history? Just the last message? A structured summary? Too little context and the worker agent asks the customer to repeat everything. Too much context and you waste tokens, increase latency, and risk the worker agent getting distracted by irrelevant information.<br>Production systems typically implement one of **_three_** state management strategies: Full context forwarding, _Structured context objects_, and Summarized context
- **Lifecycle management** (starting, monitoring, retrying, and terminating agents). 
- **Agent-first, not feature-first.** Every capability is owned by a named, scoped agent with a single responsibility.
- **State-driven pipelines.** Agents share a typed state object — they do not call each other directly. This enforces loose coupling.
- **Algorithms** Analytics, scheduling, moderation, and notifications in V1 use deterministic, explainable algorithms. AI where it adds irreplaceable value; logic where it is sufficient.
- **Deployment-ready at every commit.** Each feature branch must leave the system in a deployable state, each development follow professional methods.
- **Flat and modular.** Max two levels of nesting in the module tree. Each agent, service, and router is an independently importable Python module.
- **Claude Growth Pattern.** Four agents, two pages, one platform in V1. Validate output quality before expanding. Never build what you haven't validated a user needs.

### Agent Communication Model
```
User Intent
    │
    ▼
Orchestrator (LangGraph StateGraph)
    │
    ├── Persona Agent          → retrieves user identity context
    ├── Research/Ideation Agent → finds angles, sources, idea
    └── Composer Agent         → use content from research agent and trend agent, assembles, and create social media post content: tweet, video idea, doc, blog, etc.
    │
    ▼
Structured Output → API → Frontend
```

Agents share a single Persistent user personalization info, that contain user personalized settings, preferences, and other user-specific information. No agent holds internal state between runs. All persistence is in PostgreSQL and ChromaDB
---

## 3. V1 Agent System

### Long Term Memory
- user personalization info, user provided content

### Agent 1 — Personalization Agent

**Role:** Build, maintain, and serve a living model of the user's authentic voice, knowledge, tone, and identity.

**Inputs:**
- User onboarding profile (bio, skills, geography, field, target audience)
- User's uploaded writing samples or past posts
- User's stated interests and domain expertise
- Analysis of user social media profiles

**Outputs:**
- Persona card (structured JSON describing voice, tone, vocabulary tendencies, formality level, recurring themes)
- Top-k retrieved persona chunks (RAG retrieval from vector store)

**Core Technique:**
- Embed user writing samples using `nomic-embed-text` (local, free via Ollama)
- Store embeddings in ChromaDB with per-user namespace isolation
- At generation time, hybrid retrieve (BM25 + dense) most relevant persona chunks
- Synthesize a persona card on first setup using an LLM prompt over all user data
- Update persona card on each new sample added (incremental re-synthesis, not full rewrite)



**Free Tools Used:**
- `Ollama` (local inference) + `llama3.2` or `mistral` model
- `ChromaDB` (vector store, fully local)
- `rank_bm25` (Python, pip install, free)
- `nomic-embed-text` via Ollama (free local embeddings)
- `Arcade` - Easy authentication for reading & writing to social media platforms

---

### Agent 2 — Research & Ideation Agent

**Role:** Given the user's persona and a topic signal, autonomously research, find supporting material, and generate post angle ideas.

**Inputs:**
- Topic or keyword from user (optional — can run unprompted on a schedule)
- Persona card (from Persona Agent)
- Trend signals (from Trend Agent, injected into state)

**Outputs:**
- 3–5 post angle ideas with supporting evidence
- Source URLs and key facts
- Recommended post format per idea

**Core Technique — ReAct Loop (Reason + Act):**
```
Think: What does this user's audience care about in this topic?
Act:   Search → Tavily API (free tier, 1000 req/month) or SerpAPI
Observe: Parse results
Think: Is this enough? What angle fits the persona?
Act:   Synthesize ideation notes
Output: Structured idea list
```

**Free Tools Used:**
-  `Qwen3.5` for research and ideation topics and keywords
- `Tavily Search API` (free tier — best LLM-native search API)
- `DuckDuckGo Search` via `duckduckgo-search` Python package (fully free, no key needed)
- `trafilatura` — article content extraction (free, pip install)
- `LangGraph` — ReAct node implementation
- `LangChain` — for agent if needed
```
Cupid AI Agent
        │
        ▼
Async Research Pipeline
        │
        ▼
Local LLM Engine
        │
        ├── Qwen2.5-3B (primary)
        └── Gemma2-2B (fallback)
```

**Implementation Note:** Use `duckduckgo-search` as the primary free search provider. Fall back to Tavily free tier for richer results. Never call paid APIs.

---

### Agent 3 — Trend Intelligence Hybrid Agent

**Role:** Continuously monitor what is trending in the user's domain and surface actionable signals. Hybrid design: a rule-based algorithmic engine supervised by an AI classifier.

**Inputs:**
- User's domain tags and interest keywords
- Platform preferences
- Scheduled polling interval (configurable, default: every 6 hours)

**Outputs:**
- Ranked list of trending topics with velocity score
- Relevant trending hashtags
- Alert if a high-signal trend matches user persona

**Hybrid Architecture:**

```
Rule-Based Layer (always runs):
│
├── Fetch RSS feeds for domain keywords (feedparser, free)
├── Fetch Reddit hot posts via PRAW (free, open source)
├── Fetch HackerNews top stories via public API (free)
├── Compute TF-IDF velocity score across 24h vs 7-day baseline
├── Apply domain filter (keyword match against user tags)
└── Output: candidate trend list with raw scores

AI Supervision Layer (runs on filtered candidates):
│
├── Pass top-15 candidates to LLM with persona card
├── LLM classifies: relevant / irrelevant / high-signal
├── LLM annotates: why this is relevant to the user
└── Output: final ranked, annotated trend list
```

**Velocity Scoring Algorithm (TF-IDF adapted for trend detection):**
- Compute term frequency of topic keywords across last 24h fetched content
- Compare against rolling 7-day baseline frequency
- Velocity score = `(current_freq - baseline_freq) / (baseline_std + ε)`
- Topics with z-score > 2.0 are flagged as trending

**Free Tools Used:**
- `PRAW` — Reddit API Python wrapper (free)
- `feedparser` — RSS/Atom parsing (free, pip install)
- HackerNews Algolia API (fully free, no auth)
- `scikit-learn` — TF-IDF vectorizer for velocity scoring
- `Ollama` + local LLM for the supervision classification pass

---

### Agent 4 — Composer / Content Formatter Agent

**Role:** Take all upstream context (persona, research notes, trend signals) and produce a publication-ready, platform-specific post.

**Inputs:**
- Persona card + retrieved persona chunks
- Selected idea from Research Agent
- Trend annotations from Trend Agent
- Target platform(s): LinkedIn / Twitter-X / Threads / Reddit

**Outputs:**
- Formatted post per platform (respecting character limits, structure norms)
- Hashtag block
- Alt-text for any image prompt (if image is suggested)
- Confidence score (how well the output matches persona — computed by cosine similarity of output embedding vs persona centroid)

**Platform Formatting Rules:**
| Platform | Max Length | Structure | Hashtags |
|---|---|---|---|
| LinkedIn | 3000 chars | Hook → Body → CTA | 3–5, end of post |
| Twitter/X | 280 chars (thread for more) | Single punch or thread | 1–2 inline |
| Threads | 500 chars | Casual, conversational | Optional |
| Reddit | Unlimited | Title + body, no hashtags | None |

**Persona Fidelity Check:**
After generation, embed the output and compute cosine similarity against the user's persona centroid vector. If similarity < 0.72 threshold, trigger a regeneration pass with tighter persona constraints. This is a deterministic quality gate, not another LLM call — it uses the already-computed embeddings.

**Free Tools Used:**
- Open source xAI Grok-1 for generating real human like post description, captions and tweets.
- `ChromaDB` for persona centroid lookup
- `sentence-transformers` for fidelity scoring (local, free)

---

## 4. Non-Agent Intelligence Layer

These capabilities exist in V1 but use **deterministic algorithms**, not LLM agents. This is intentional — following the same engineering philosophy used by Anthropic, Google, and Meta internally: *AI where it creates irreplaceable value, algorithms where logic suffices.*

### Analytics Engine (Algorithm-Based)

**Metrics computed without AI:**
- Engagement rate: `(likes + comments + shares) / impressions × 100`
- Best performing post type: frequency count + average engagement by format tag
- Peak engagement window: aggregate hourly engagement across post history, compute distribution, surface top 3 hours
- Audience growth rate: 7-day rolling delta on follower count
- Topic performance index: group posts by topic tag, rank by mean engagement

**Implementation:** Pure Python + SQLAlchemy aggregate queries. No ML.

### Scheduling Optimizer (Algorithm-Based)

Uses a rule-based time-slot scoring system:
1. Parse user's timezone from profile
2. Load global engagement window research (hardcoded lookup table per platform, sourced from Buffer/Sprout Social research)
3. Score each candidate time slot: `platform_weight × timezone_adjusted_score × audience_overlap_factor`
4. Return top 3 slots per platform per day
5. Store as Celery beat schedule

**No AI involved.** This is a weighted lookup with timezone normalization.

### Brand Safety / Moderation (Algorithm-Based)

Three layers, no LLM:
1. **Blocklist filter** — regex match against a curated list of platform-violation keywords (maintained in a flat JSON file, easy to update)
2. **PII detector** — `presidio-analyzer` (Microsoft open-source, free) — detects phone numbers, emails, addresses, IDs before publish
3. **Sentiment gate** — `VADER` sentiment analysis (NLTK, free, no API) — blocks posts with compound sentiment score < -0.6 (highly negative) and requires user confirmation

### Notification System (Algorithm-Based)

- In-app notifications via PostgreSQL `notifications` table + polling (Server-Sent Events for real-time feel)
- Email notifications via `Resend` free tier (3000 emails/month free) or self-hosted `Postal`
- No push notifications in V1

---

## 5. Tech Stack

### Backend
| Component | Tool | Reason |
|---|---|---|
| API Framework | `FastAPI` | Async-native, perfect for concurrent LLM calls, auto OpenAPI docs |
| Task Queue | `Celery` + Redis | Distributed agent job execution, scheduled tasks |
| Database | `PostgreSQL` | Relational core: users, posts, analytics |
| Cache / Queue Broker | `Redis` | Celery broker, rate limiting, trend cache |
| Vector Store | `ChromaDB` | Local, zero-config, per-user namespace support |
| LLM Runtime | `HuggingFace` | 100% local, zero cost, supports llama3/mistral/gemma |

### AI & Agents
| Component | Tool | Reason |
|---|---|---|
| Agent Orchestration | `LangGraph` | Stateful DAG-based agent pipelines, Apache 2.0 |
| LLM Interface | `LangChain` (core only) | Tool calling, prompt templates, output parsers |
| Embeddings | `nomic-embed-text` via Ollama | Free, local, high quality |
| Semantic Similarity | `sentence-transformers` | Local inference, persona fidelity scoring |
| Trend NLP | `scikit-learn` TF-IDF | Velocity scoring on trend candidates |
| Sentiment | `VADER` (NLTK) | Brand safety gate, no API needed |
| PII Detection | `presidio-analyzer` (Microsoft) | Open source, production grade |

### Frontend
| Component | Tool |
|---|---|
| Framework | `Next.js 14` (App Router) |
| UI Components | `shadcn/ui` |
| Styling | `Tailwind CSS v4` |
| State Management | `Zustand` |
| Data Fetching | `TanStack Query` (React Query) |
| Charts / Analytics | `Recharts` (free, open source) |
| Forms | `React Hook Form` + `Zod` |

### Infrastructure (Free Tier Deployable)
| Component | Tool | Free Tier |
|---|---|---|
| Hosting (Backend) | `Railway` or `Render` | $5 credit / free tier |
| Hosting (Frontend) | `Vercel` | Free |
| Database | `Supabase` (PostgreSQL) | 500MB free |
| Redis | `Upstash` | 10k commands/day free |
| Vector DB | `ChromaDB` (self-hosted on backend) | Free |
| Containerization | `Docker` + `Docker Compose` | Free |

### Social APIs (Free Tiers)
| Platform | API | Free Limit |
|---|---|---|
| Reddit | PRAW (read) | No posting in V1, read-only trend data |
| HackerNews | Algolia public API | Unlimited, free |
| RSS Feeds | `feedparser` | Unlimited |
| Twitter/X | Basic API v2 | 1500 posts/month write (free tier) |
| LinkedIn | OAuth API | Free for posting to own profile |

---

## 6. Agent Framework & SDK Guide

### Primary Framework: LangGraph

**What it is:** A graph-based agent orchestration library from LangChain Inc. Licensed Apache 2.0. Agents are nodes in a `StateGraph`. Data flows as a typed state dict through edges. Conditional routing enables supervisor logic.

**Why not alternatives:**
- `CrewAI` — opinionated, less control over state, harder to debug
- `AutoGen` (Microsoft) — conversation-based, better for multi-LLM debates, not production pipelines
- `raw LangChain chains` — no state management, breaks on complex routing
- `Haystack` — good but heavier, more NLP-document-pipeline oriented


## 7. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js)                         │
│  Dashboard │ Trends Page │ Recommendations │ Schedule │ Analytics   │
└─────────────────┬───────────────────────────────────────────────────┘
                  │  REST / SSE
┌─────────────────▼───────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                              │
│  /auth  │  /agents  │  /posts  │  /trends  │  /analytics  │  /ws    │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
     ┌────────────┴──────────────┐
     │                           │
┌────▼────────────────┐   ┌──────▼──────────────────────────────────┐
│  PostgreSQL         │   │         CELERY WORKERS                  │
│  - users            │   │  ┌──────────────────────────────────┐   │
│  - posts            │   │  │        LANGGRAPH PIPELINE        │   │
│  - persona_profiles │   │  │                                  │   │
│  - analytics        │   │  │  Persona → Research → Trend →    │   │
│  - notifications    │   │  │              Composer            │   │
│  - schedules        │   │  └──────────────────────────────────┘   │
└─────────────────────┘   │                                         │
                          │  Non-Agent Workers:                     │
┌─────────────────────┐   │  - Analytics Aggregator (cron)          │
│  ChromaDB           │   │  - Scheduler Optimizer (cron)           │
│  (per-user          │◄──┤  - Brand Safety Filter                  │
│   namespaces)       │   │  - Notification Dispatcher              │
└─────────────────────┘   └──────────────────┬──────────────────────┘
                                              │
┌─────────────────────┐              ┌────────▼─────────────┐
│  hugginface         │◄─────────────│  Redis               │
│ Model               │              │  (broker + cache)    │
└─────────────────────┘              └──────────────────────┘
```

---

## 8. Database Schema

```sql
-- Users
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
    password    VARCHAR(255) NOT NULL,
);

-- Persona Profiles
CREATE TABLE persona_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    persona_card    JSONB NOT NULL,
    version         INT DEFAULT 1,
    chroma_namespace VARCHAR(100) NOT NULL,  -- ChromaDB collection name
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- User Platform Connections
CREATE TABLE platform_connections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    platform    VARCHAR(50) NOT NULL,         -- linkedin, twitter, threads
    access_token TEXT,                         -- encrypted
    expires_at  TIMESTAMP,
    is_active   BOOLEAN DEFAULT TRUE
);

-- Trend Cache
CREATE TABLE trend_cache (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    topic       VARCHAR(255),
    velocity_score FLOAT,
    source      VARCHAR(50),    -- reddit, hackernews, rss
    raw_data    JSONB,
    expires_at  TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Notifications
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    type        VARCHAR(50),    -- trend_alert, post_published, analytics_summary
    message     TEXT,
    is_read     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## 9. API Design Conventions

- **Base URL:** `/api/v1/`
- **Auth:** JWT (via `python-jose`) + HTTP-only cookie
- **Response envelope:**
```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": { "version": "1.0", "request_id": "uuid" }
}
```
- **Agent endpoints are async and return a `run_id`** — the client polls `/agents/runs/{run_id}` for status. Never block on agent completion in a single HTTP request.
- **All agent runs are idempotent** — retrying the same `run_id` returns the cached result.

### Core Endpoint Groups
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout

POST   /api/v1/persona/setup          → triggers Persona Agent setup job
GET    /api/v1/persona/card           → fetch current persona card
POST   /api/v1/persona/samples        → upload writing samples

POST   /api/v1/agents/generate        → trigger full pipeline (returns run_id)
GET    /api/v1/agents/runs/{run_id}   → poll run status + result

GET    /api/v1/trends                 → fetch latest trend cache for user
GET    /api/v1/recommendations        → fetch Research Agent ideation list


GET    /api/v1/notifications          → list unread notifications
PATCH  /api/v1/notifications/{id}/read
```

### UI and frontend styling and theme
* social media inspire theme, minimal but creative to avoid boring and confuing look
* icons for page navigation instead of text (in header)
* primary color code: #d47a03
* border and text color: #2a3852
* background color: #fff6ed or #fff9f3

---

## 10. Project Structure

```
cupid/
│
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # Settings via pydantic-settings
│   │   │
│   │   ├── agents/                   # LangGraph agent nodes
│   │   │   ├── state.py              # CupidState TypedDict
│   │   │   ├── graph.py              # StateGraph assembly
│   │   │   ├── persona.py            # Persona Agent node
│   │   │   ├── research.py           # Research/Ideation Agent node
│   │   │   ├── trend.py              # Trend Intelligence Agent node
│   │   │   └── composer.py           # Composer Agent node
│   │   │
│   │   ├── services/                 # Non-agent intelligence
│   │   │   ├── analytics.py          # Engagement metric aggregation
│   │   │   ├── scheduler.py          # Time-slot scoring algorithm
│   │   │   ├── brand_safety.py       # Blocklist + PII + VADER
│   │   │   └── notifications.py      # Notification dispatch
│   │   │
│   │   ├── routers/                  # FastAPI route handlers
│   │   │   ├── auth.py
│   │   │   ├── persona.py
│   │   │   ├── agents.py
│   │   │   ├── trends.py
│   │   │   ├── analytics.py
│   │   │   └── notifications.py
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   └── notification.py
│   │   │
│   │   ├── core/                     # Shared infrastructure
│   │   │   ├── db.py                 # PostgreSQL session
│   │   │   ├── redis.py              # Redis client
│   │   │   ├── vector_store.py       # ChromaDB client + per-user n
│   │
│   ├── alembic/                      # DB migration files
│   ├── tests/                        # pytest test suite
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── frontend/
│   ├── app/                          # Next.js App Router
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (dashboard)/
│   │   └── page.tsx (defaul home page with simple no authentication, login button initially for MVP)
|   |   └── layout.tsx
│   │
│   ├── components/
│   │   ├── ui/                       # shadcn/ui components
│   │   ├── header/                   # logo on left and page button on right
│   │   ├── agents/                   # agent run status widgets
│   │   ├── posts/                    # post editor, preview, card
│   │   └── charts/                   # Recharts wrappers
│   │
│   ├── lib/
│   │   ├── api.ts                    # typed API client
│   │   ├── store.ts                  # Zustand global state
│   │   └── utils.ts
│   │
└── README/