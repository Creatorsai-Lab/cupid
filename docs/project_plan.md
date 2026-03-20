# Cupid — Project Plan

> **"Social media soulmate"**

---

## How to Position and Present Cupid

Cupid is team of Mixture of Experts ai agents. It is a **personal AI agent system** that learns who you are — your voice, expertise, geography, and audience — and autonomously operates your professional social presence through a coordinated pipeline of specialized agents. Where every other tool hands you a template, Cupid deploys agents that think, research, and write the way you do. The Persona Agent alone makes Cupid categorically different: it builds a living, evolving model of the user that no scheduler, AI writer, or automation tool has ever attempted at the individual creator level. Cupid's output does not read like AI. It reads like you — because its entire architecture is built around that single goal.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [V1 Agent System — Four Agents](#3-v1-agent-system)
4. [V1 Non-Agent Intelligence Layer](#4-v1-non-agent-intelligence-layer)
5. [Tech Stack — Free & Open Source](#5-tech-stack)
6. [Agent Framework & SDK Guide](#6-agent-framework--sdk-guide)
7. [System Architecture Diagram](#7-system-architecture-diagram)
8. [Database Schema — Core Tables](#8-database-schema)
9. [API Design Conventions](#9-api-design-conventions)
10. [Project Structure](#10-project-structure)
11. [Development Roadmap — Agile Phases](#11-development-roadmap)
12. [Deployment Strategy](#12-deployment-strategy)
13. [Key Algorithms Reference](#13-key-algorithms-reference)

---

## 1. Project Overview

| Field | Detail |
|---|---|
| **Name** | Cupid |
| **Tagline** | Agents That Post Authentically |
| **Category** | Personal AI Agent System |
| **Target User** | Individual professionals, researchers, engineers, founders building a personal brand |
| **Core Thesis** | Persona fidelity at the agent level is an unsolved problem. Every existing tool treats voice as a prompt parameter. Cupid treats it as a trained, retrievable, continuously refined identity model. |
| **License** | MIT |
| **Budget** | Zero. Fully FOSS and free-tier infrastructure. |

---

## 2. Architecture Philosophy

### Principles
- for Swarm architecture agent orchestration debuuuging we need specialized tooling (distributed tracing, event sourcing, blackboard snapshots).
- Without an orchestrator deciding when to stop, swarm agents need explicit termination conditions , max iterations, quality thresholds, or timeout-based convergence. Design these conditions carefully; too-aggressive termination produces incomplete results, while too-conservative termination burns tokens and compute.
- **Task routing** (which agent handles each subtask), **context flow** (how information is passed between agents), and **lifecycle management** (how agents start, fail, retry, and terminate).
- At the implementation level, orchestration will involves four components: **a registry** of available agents (4 as of now) and their capabilities, a **router** that maps incoming tasks to the best agent or sequence of agents, a **state store** for shared context and conversation history, user persona, and a **supervisor system** that monitors timeouts, retries, and escalations.
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
    ├── Research/Ideation Agent → finds angles, sources, ideas
    ├── Trend Intelligence Agent → showcases trending topics, recommended hashtags, timing suggestions
    └── Composer Agent         → assembles final platform-specific post
    │
    ▼
Structured Output → API → Frontend
```

Agents share a single `CupidState` TypedDict. No agent holds internal state between runs. All persistence is in PostgreSQL and ChromaDB.

---

## 3. V1 Agent System

### Long Term Memory
- User details, info, demographics, skills, interests, expertise, audience, geography, domain, past posts, writing samples, writing rules, persona prompt template.

### Agent 1 — Persona Agent

**Role:** Build, maintain, and serve a living model of the user's authentic voice, knowledge, tone, and identity.

**Inputs:**
- User onboarding profile (bio, skills, geography, field, target audience)
- User's uploaded writing samples or past posts
- User's stated interests and domain expertise

**Outputs:**
- Persona card (structured JSON describing voice, tone, vocabulary tendencies, formality level, recurring themes)
- Top-k retrieved persona chunks (RAG retrieval from vector store)

**Core Technique:**
- Embed user writing samples using `nomic-embed-text` (local, free via Ollama)
- Store embeddings in ChromaDB with per-user namespace isolation
- At generation time, hybrid retrieve (BM25 + dense) most relevant persona chunks
- Synthesize a persona card on first setup using an LLM prompt over all user data
- Update persona card on each new sample added (incremental re-synthesis, not full rewrite)

**Persona Card Schema:**
```json
{
  "user_id": "uuid",
  "tone": "analytical and direct",
  "bio": "tech and business content creator",
  "formality": "semi-formal",
  "avg_sentence_length": "medium",
  "vocabulary_bias": ["systems thinking", "open source", "research-backed"],
  "structural_preference": "short hook → reasoning → call-to-action",
  "avoid": ["corporate jargon", "motivational clichés"],
  "geography_signals": ["India", "tier-2 city", "South Asian context"],
  "domain": "AI/ML engineering",
  "audience": "technical professionals, indie hackers, AI researchers"
}
```

**Free Tools Used:**
- `Ollama` (local inference) + `llama3.2` or `mistral` model
- `ChromaDB` (vector store, fully local)
- `rank_bm25` (Python, pip install, free)
- `nomic-embed-text` via Ollama (free local embeddings)

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
- `newspaper3k` or `trafilatura` — article content extraction (free, pip install)
- `LangGraph` — ReAct node implementation

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
| LLM Runtime | `Ollama` | 100% local, zero cost, supports llama3/mistral/gemma |

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

**LangGraph Core Concepts You Must Know:**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# 1. Define shared state
class CupidState(TypedDict):
    user_id: str
    topic: str
    persona_card: dict
    persona_chunks: list[str]
    trend_data: list[dict]
    research_notes: list[str]
    draft: dict[str, str]        # platform → draft post
    fidelity_score: float
    ready_to_publish: bool

# 2. Define agent nodes (each is a pure function)
def persona_agent(state: CupidState) -> CupidState:
    # retrieve from ChromaDB, build persona card
    ...
    return {**state, "persona_card": card, "persona_chunks": chunks}

def composer_agent(state: CupidState) -> CupidState:
    # generate post using persona + research + trends
    ...
    return {**state, "draft": drafts, "fidelity_score": score}

# 3. Define routing logic
def route_after_composer(state: CupidState) -> str:
    if state["fidelity_score"] < 0.72:
        return "composer_agent"   # retry
    return END

# 4. Build the graph
graph = StateGraph(CupidState)
graph.add_node("persona_agent", persona_agent)
graph.add_node("research_agent", research_agent)
graph.add_node("trend_agent", trend_agent)
graph.add_node("composer_agent", composer_agent)

graph.set_entry_point("persona_agent")
graph.add_edge("persona_agent", "research_agent")
graph.add_edge("research_agent", "trend_agent")
graph.add_edge("trend_agent", "composer_agent")
graph.add_conditional_edges("composer_agent", route_after_composer)

pipeline = graph.compile()
```

**LangSmith (Free Tier):** Use for agent trace observability. Every LangGraph run is automatically traced. Essential for debugging agent behavior in development.

### Supporting Libraries

| Library | Purpose | Install |
|---|---|---|
| `langchain-core` | Prompt templates, output parsers, tool calling | `pip install langchain-core` |
| `langchain-ollama` | Ollama LLM integration for LangChain | `pip install langchain-ollama` |
| `langgraph` | Agent graph orchestration | `pip install langgraph` |
| `chromadb` | Vector store | `pip install chromadb` |
| `sentence-transformers` | Local embeddings + fidelity scoring | `pip install sentence-transformers` |
| `rank_bm25` | Sparse retrieval for hybrid RAG | `pip install rank-bm25` |
| `praw` | Reddit trend data | `pip install praw` |
| `feedparser` | RSS feed parsing | `pip install feedparser` |
| `trafilatura` | Article content extraction | `pip install trafilatura` |
| `duckduckgo-search` | Free web search for Research Agent | `pip install duckduckgo-search` |
| `presidio-analyzer` | PII detection | `pip install presidio-analyzer` |
| `nltk` (VADER) | Sentiment analysis | `pip install nltk` |
| `scikit-learn` | TF-IDF trend scoring | `pip install scikit-learn` |
| `celery[redis]` | Task queue | `pip install celery[redis]` |
| `fastapi` | API server | `pip install fastapi` |
| `sqlalchemy` | ORM | `pip install sqlalchemy` |
| `alembic` | DB migrations | `pip install alembic` |

---

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
│  Ollama (Local LLM) │◄─────────────│  Redis               │
│  llama3.2 / mistral │              │  (broker + cache)    │
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

-- Posts
CREATE TABLE posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    platform        VARCHAR(50) NOT NULL,
    content         TEXT NOT NULL,
    status          VARCHAR(20) DEFAULT 'draft',  -- draft/scheduled/published/failed
    fidelity_score  FLOAT,
    scheduled_at    TIMESTAMP,
    published_at    TIMESTAMP,
    agent_run_id    VARCHAR(100),   -- LangGraph run trace ID
    metadata        JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Post Analytics
CREATE TABLE post_analytics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id     UUID REFERENCES posts(id),
    impressions INT DEFAULT 0,
    likes       INT DEFAULT 0,
    comments    INT DEFAULT 0,
    shares      INT DEFAULT 0,
    clicks      INT DEFAULT 0,
    fetched_at  TIMESTAMP DEFAULT NOW()
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

GET    /api/v1/posts                  → list posts (draft/scheduled/published)
POST   /api/v1/posts/{id}/schedule    → schedule a post
POST   /api/v1/posts/{id}/publish     → immediate publish
DELETE /api/v1/posts/{id}

GET    /api/v1/analytics/summary      → aggregated engagement metrics
GET    /api/v1/analytics/posts        → per-post performance

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
│   │   │   ├── posts.py
│   │   │   ├── analytics.py
│   │   │   └── notifications.py
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── post.py
│   │   │   ├── analytics.py
│   │   │   └── notification.py
│   │   │
│   │   ├── core/                     # Shared infrastructure
│   │   │   ├── db.py                 # PostgreSQL session
│   │   │   ├── redis.py              # Redis client
│   │   │   ├── vector_store.py       # ChromaDB client + per-user namespacing
│   │   │   ├── llm.py                # Ollama LLM + embedding client
│   │   │   └── security.py           # JWT, token encryption
│   │   │
│   │   └── workers/                  # Celery task definitions
│   │       ├── celery_app.py
│   │       ├── agent_tasks.py        # async agent pipeline trigger
│   │       ├── trend_tasks.py        # scheduled trend fetching
│   │       └── analytics_tasks.py    # scheduled analytics aggregation
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
│   │   │   ├── layout.tsx
│   │   │   ├── trends/page.tsx
│   │   │   ├── recommendations/page.tsx
│   │   │   ├── schedule/page.tsx
│   │   │   └── analytics/page.tsx
│   │   └── page.tsx (defaul home page with simple no authentication login button)
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
│   └── hooks/
│       ├── useAgentRun.ts            # polling hook for agent run_id
│       └── useNotifications.ts       # SSE listener
│
└── docs/
    ├── project_plan.md               # this file
    ├── architecture.md
    └── api_reference.md
```

---

## 11. Development Roadmap — Agile Phases

### Phase 0 — Foundation (Week 1–2)
- [ ] Repo init, Docker Compose with FastAPI + PostgreSQL + Redis + Ollama
- [ ] Alembic migrations for all core tables
- [ ] JWT auth with register/login endpoints
- [ ] ChromaDB client with per-user namespace utility
- [ ] Next.js project init with shadcn/ui + Tailwind configured
- [ ] Login + Register UI pages
- [ ] `GET /health` endpoint, CI pipeline (GitHub Actions, free)

**Milestone: System runs locally end-to-end. Auth works. DB migrates clean.**

### Phase 1 — Persona Agent (Week 3–4)
- [ ] Onboarding form UI (bio, skills, interests, geography, audience)
- [ ] Writing sample upload (paste or file)
- [ ] Persona Agent node: embedding pipeline + ChromaDB ingestion
- [ ] Persona card synthesis using Ollama
- [ ] `POST /persona/setup`, `GET /persona/card` endpoints
- [ ] Persona card display component in dashboard

**Milestone: User can set up their persona and view their generated persona card.**

### Phase 2 — Trend Intelligence Agent (Week 5–6)
- [ ] RSS feed fetcher (Celery beat task, every 6h)
- [ ] Reddit PRAW integration (domain-filtered hot posts)
- [ ] HackerNews Algolia API integration
- [ ] TF-IDF velocity scoring pipeline
- [ ] AI supervision classification pass (Ollama)
- [ ] Trends page UI with velocity scores + source labels
- [ ] Trend cache database layer

**Milestone: Trends page shows live, scored, persona-relevant trending topics.**

### Phase 3 — Research + Composer Agents (Week 7–9)
- [ ] LangGraph StateGraph assembly (all 4 agent nodes)
- [ ] Research Agent: DuckDuckGo search + ReAct loop + ideation synthesis
- [ ] Composer Agent: platform-specific formatting + persona fidelity scoring
- [ ] Recommendations page UI (ideation list with angle cards)
- [ ] Post editor UI with platform toggle, character count, fidelity score indicator
- [ ] `POST /agents/generate` + polling endpoint
- [ ] Draft saving + post status management

**Milestone: User can trigger the full agent pipeline and receive a platform-specific draft.**

### Phase 4 — Non-Agent Intelligence Layer (Week 10–11)
- [ ] Brand Safety filter (blocklist + Presidio + VADER) — pre-publish gate
- [ ] Scheduling algorithm + time-slot scoring
- [ ] Schedule page UI (calendar view, drag-to-schedule)
- [ ] LinkedIn OAuth + posting API integration
- [ ] Analytics aggregation worker (Celery beat)
- [ ] Analytics page UI (Recharts: engagement rate, top posts, growth curve)
- [ ] SSE notification system + in-app notification bell

**Milestone: Full V1 feature set complete. Posts can be scheduled and published.**

### Phase 5 — Hardening & Deployment (Week 12)
- [ ] Rate limiting (slowapi, per-user per-endpoint)
- [ ] Error boundary audit across all agent nodes
- [ ] pytest coverage > 70% for all service + agent modules
- [ ] Docker Compose production config (separate from dev)
- [ ] Deploy: Railway (backend) + Vercel (frontend) + Supabase (prod DB)
- [ ] README with setup instructions + demo GIF

**Milestone: Cupid is live at a public URL.**

---

## 12. Deployment Strategy

### Local Development
```bash
docker-compose up          # PostgreSQL + Redis + ChromaDB + Ollama
uvicorn app.main:app --reload --port 8000
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat   # scheduled tasks
```

### Environment Variables (`.env`)
```env
DATABASE_URL=postgresql://cupid:password@localhost:5432/cupid
REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
CHROMA_PERSIST_DIR=./chroma_data
JWT_SECRET_KEY=your-256-bit-secret
JWT_ALGORITHM=HS256
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=cupid/1.0
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
```

### Production (Free Tier)
```
Backend     → Railway.app         (free $5 credit / month, always-on)
Frontend    → Vercel               (free, auto-deploy on push)
Database    → Supabase             (500MB PostgreSQL free)
Redis       → Upstash              (10k commands/day free)
LLM         → Ollama on Railway    (run in same container as backend)
ChromaDB    → Filesystem on Railway (persisted volume)
```

### Branch Strategy
```
main          → production-ready at all times
dev           → integration branch
feature/*     → individual feature branches
```
Merge `feature/*` → `dev` via PR. Merge `dev` → `main` only when phase milestone is complete.

---

## 13. Key Algorithms Reference

### Hybrid RAG for Persona Retrieval
```python
# Dense retrieval (semantic)
dense_results = chroma_collection.query(query_texts=[query], n_results=20)

# Sparse retrieval (keyword, BM25)
bm25 = BM25Okapi(corpus_tokens)
sparse_scores = bm25.get_scores(query_tokens)

# Reciprocal Rank Fusion
def rrf(dense_ranks, sparse_ranks, k=60):
    scores = {}
    for rank, doc_id in enumerate(dense_ranks):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    for rank, doc_id in enumerate(sparse_ranks):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### TF-IDF Trend Velocity Scoring
```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

def compute_velocity(current_docs: list[str], baseline_docs: list[str]) -> dict:
    all_docs = current_docs + baseline_docs
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(all_docs)
    
    current_mean = tfidf_matrix[:len(current_docs)].mean(axis=0)
    baseline_mean = tfidf_matrix[len(current_docs):].mean(axis=0)
    baseline_std = np.asarray(tfidf_matrix[len(current_docs):].todense()).std(axis=0) + 1e-8
    
    velocity = (np.asarray(current_mean) - np.asarray(baseline_mean)) / baseline_std
    terms = vectorizer.get_feature_names_out()
    return dict(sorted(zip(terms, velocity.flatten()), key=lambda x: x[1], reverse=True)[:50])
```

### Persona Fidelity Score
```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')  # local, free, fast

def fidelity_score(draft: str, persona_chunks: list[str]) -> float:
    draft_embedding = model.encode([draft])
    persona_embeddings = model.encode(persona_chunks)
    persona_centroid = np.mean(persona_embeddings, axis=0, keepdims=True)
    score = cosine_similarity(draft_embedding, persona_centroid)[0][0]
    return float(score)
```

### Scheduling Time-Slot Scorer
```python
# Platform engagement windows (sourced from industry research)
ENGAGEMENT_WINDOWS = {
    "linkedin": [(8, 10), (12, 13), (17, 18)],   # UTC hours, adjust to user tz
    "twitter":  [(9, 10), (13, 15), (19, 21)],
    "threads":  [(11, 13), (19, 22)],
}

def score_slot(platform: str, hour_utc: int, user_timezone_offset: int) -> float:
    local_hour = (hour_utc + user_timezone_offset) % 24
    windows = ENGAGEMENT_WINDOWS.get(platform, [])
    for start, end in windows:
        if start <= local_hour <= end:
            # Peak window: score based on proximity to window center
            center = (start + end) / 2
            proximity = 1 - abs(local_hour - center) / ((end - start) / 2)
            return round(proximity, 3)
    return 0.1  # off-peak baseline
```

---

### Learning Needed
1. RAG (Retrieval-Augmented Generation) — Persona Engine Core
> Key technique: Hybrid search (BM25 sparse + dense embedding) gives better retrieval than pure semantic search for persona data.
2. ReAct Pattern (Reasoning + Acting) — Research Agent:
Research Agent needs to reason about what to search, execute the search, observe the result, and decide whether to search again. This is the ReAct loop. LangGraph implements this natively. Study the original ReAct paper (Yao et al., 2022) — it's directly applicable.
3. LLM Persona Mimicry Techniques: Few-shot prompting with user's own posts, Style embedding extraction, Persona prompt template synthesis. 
4.  Multi-Agent Orchestration with LangGraph and System design for multi-tenant AI
5. Feedback Loop & Continuous Persona: Score the post (engagement_rate / baseline)
Tag it (high-performer / low-performer)
Store the tagged post back into the vector DB with performance metadata
On next generation, retrieve high-performers with higher weight
> This is a simple but powerful reinforcement signal without RL — it's essentially a reranking heuristic over the persona vector store.
6. Rate Limiting & API Safety Architecture
7. Async Python: asyncio, httpx
8. Celery + Redis task architecture — distributed job queues, beat scheduler for the scheduling agent
7. Embeddings, Vector Similarity, and Nearest-Neighbor Search
4. Agent Frameworks (LangChain)
5. Retrieval Libraries (LlamaIndex)
6. Practical Infra: Docker, Container Orchestration (K8s Basics), CI/CD Pipelines
