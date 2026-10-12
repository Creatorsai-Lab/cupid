# Cupid — Updated Version Plan

> Living plan for rebuilding Cupid's agent system. Edit freely: tick tasks as they land,
> add decisions to the log, and keep "Open questions" current.
>
> Last updated: 2026-10-12

---

## 1. Goal

Rebuild Cupid's agent system — runtime, harness and agents — so it is robust, fast, easy to
change and cheap to run on free LLM tiers, without over-engineering. The studio (content
creation) is the product; every other step exists to feed it well.

---

## 2. Decision log

| #   | Decision                                                                                                                                              | Date       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| D1  | Agent endpoints stay under `/api/v1/agents`. New routes are added there (pre-launch, no v2).                                                         | 2026-10-06 |
| D2  | Keep `_TONE_TO_VOICE`: one copy in `studio/voices.py`, every tone mapped, actually read by the studio.                                               | 2026-10-06 |
| D3  | The new research agent (`D:\cupid_agents\web-search-agent`) replaces both the personalization and research agents.                                    | 2026-10-06 |
| D4  | Workflow outside, agents inside: a fixed LangGraph pipeline with intelligence inside each step. No swarm.                                            | 2026-10-06 |
| D5  | Free LLM APIs only until a working MVP. Each role has an ordered provider list; one provider per role for a whole run; skip a provider while it is rate-limited. | 2026-10-09 |
| D6  | Send as little user data to LLMs as possible; use provider settings and request options that disable logging and training.                          | 2026-10-09 |
| D7  | Prompt caching from the first step (see 5.5).                                                                                                        | 2026-10-09 |
| D8  | No research-output compression until the optimization phase (Phase 6).                                                                              | 2026-10-09 |
| D9  | Composer renamed **studio**: head agent **director**, sub-agents **specialists**, later a lightweight **editor**. Not "creator" — that is our user.  | 2026-10-09 |
| D10 | Studio output is stored as typed, addressable blocks — never plain text.                                                                             | 2026-10-09 |
| D11 | Tones are defined once per language (one Python type, one TypeScript constant).                                                                      | 2026-10-09 |
| D12 | Feature folders: every feature and every agent owns its `models.py`. No top-level `models/`, `schemas/`, `services/`, `routers/`.                    | 2026-10-09 |
| D13 | Folder depth is `app/<feature>/<file>`; only agents go one level deeper.                                                                             | 2026-10-09 |
| D14 | Trends ingestion is rebuilt from scratch later; no piecemeal fixes until then.                                                                       | 2026-10-09 |
| D15 | The first pipeline step keeps the name **supervisor** (`agents/supervisor/`); it will gain more files in later versions.                             | 2026-10-09 |
| D16 | The supervisor makes no LLM calls — every check is deterministic.                                                                                    | 2026-10-09 |
| D17 | uv is the Python dependency manager: `pyproject.toml` + `uv.lock`, commands via `uv run` (no venv activation).                                       | 2026-10-09 |
| D18 | No git pre-commit hooks. Quality checks are run manually with `uv run`: ruff (lint + format), pyright (types), pytest; CI runs them on pull requests. | 2026-10-12 |
| D19 | Evals live in `backend/evals/`, separate from `tests/`: real LLMs, scored datasets, results gitignored; never run by `uv run pytest` or CI. | 2026-10-12 |
| D20 | Test layout: folder = what is tested (mirrors `app/`, agents get one subfolder per part); marker = what it needs (`db`, `integration`). `tests/security/` holds only app-wide security rules; feature-specific security tests live with the feature. Ruff security rules (`S`) are on. | 2026-10-12 |

---

## 3. Pipeline

```
POST /api/v1/agents/generate ──► run_id
        │
     worker (queue) ── LangGraph pipeline, state checkpointed in Postgres per run
        │
     supervisor ──► research ──► studio: director ──► specialists, in parallel ──► finalize
                                                (each: make → review → one rewrite if needed)

     every LLM call ──► LLM gateway (roles, one provider per run, retries, usage logging)
     every step     ──► typed events ──► Redis stream ──► GET /runs/{id}/events (SSE)
```

| Step        | Job                                                                                                                                  | Writes to the run pool   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| supervisor  | Deterministic checks (input, quota, rate limits) and the run plan from the request. No LLM call. Replaces the keyword supervisor. | `plan`                   |
| research    | Plan queries, search, extract, evaluate and select personalized sources.                                                             | `research`               |
| director    | Reads everything once and makes the creative decisions every specialist follows.                                                     | `brief`                  |
| specialists | Produce each deliverable variant in parallel. Writer first; designer, infographic, animator and video later. Each piece is reviewed before it lands. | `pieces` (appended)      |
| finalize    | Save to history once (keyed by run id) and emit `run.completed`.                                                                     | —                        |

### Principles

1. **Workflow outside, agents inside.** The order of steps is fixed in code; reasoning happens inside steps.
2. **One shared run pool, one owner per key.** Steps read anything, write only what they own.
3. **The director decides once.** Specialists build from the same brief, so outputs stay consistent.
4. **Resume from the step that failed,** never from scratch.
5. **Expected outcomes are typed statuses.** Exceptions mean "unexpected".
6. **Cheap by design.** Stable prompt prefixes, one provider per role per run, parallel only where work is independent.
7. **Measure before optimizing.** Evals and logged tokens decide changes, not guesses.
8. **Simplest thing that works.** A file exists only when it has code.

---

## 4. Code organization

### 4.1 Feature-folder convention

| File         | Job                                                                                   |
| ------------ | ------------------------------------------------------------------------------------- |
| `models.py`  | Data this folder owns: DB tables in features, typed contracts (Pydantic) in agents.   |
| `schemas.py` | HTTP request and response shapes only.                                                |
| `service.py` | Logic.                                                                                |
| `router.py`  | HTTP only, thin. No try/except, no business logic.                                    |
| `deps.py`    | FastAPI dependencies.                                                                 |

Rules:

- Create a file only when there is code for it. No empty skeleton files.
- Depth: `app/<feature>/<file>`. Only agents go one level deeper.
- Imports flow one way: router → service → models. Features may use other features' models
  and services. Nothing imports a router. `core/` imports no feature.
- "Model" means DB table or contract depending on the folder. In agent code, say "LLM" or
  "model role" for AI models, never "model" alone.

### 4.2 Target layout

```
backend/app/
  main.py            app setup: routers, error handler, startup/shutdown
  config.py          settings (unchanged)
  core/              shared infrastructure, imports no feature
    db.py            engine, session, Base, DbSession
    tables.py        discovers every models.py so Alembic and SQLAlchemy see all tables
    errors.py        AppError family
    redis.py  logging_config.py  oauth_state.py
  auth/              models.py (User)  schemas.py  service.py  router.py  deps.py
                     google.py (login OAuth)  session.py (JWT + cookie)
  profile/           models.py  schemas.py  service.py  router.py
  connections/       models.py  schemas.py  router.py  youtube_oauth.py  token_crypto.py
  insights/          models.py (snapshot, top content)  schemas.py  service.py  router.py
                     sync.py  youtube_client.py  token_manager.py  scheduler.py
  history/           models.py  schemas.py  service.py  router.py
  trends/            models.py  schemas.py  service.py  router.py  ingest.py  ranker.py
                     source_client.py  scheduler.py   (moved as-is; rebuilt later, D14)
  admin/             models.py (AuditLog)  setup.py  security.py  dashboard_view.py
  earn/              unchanged
  subscriptions/     unchanged
  agents/
    router.py  schemas.py
    models.py        shared contracts: Tone, RunRequest, RunEvent, Issue
    state.py         the run pool
    graph.py         wiring only
    runtime/         runner.py  events.py  worker.py  checkpoint.py
    llm/             gateway.py  roles.py  prompts.py  errors.py
    supervisor/      models.py  agent.py
    research/        models.py  agent.py  planning.py  filters.py  providers.py  config.py  adapter.py
    studio/          models.py  director.py  registry.py  reviewer.py  voices.py
                     specialists/writer.py   (later: designer, infographic, animator, video)
                     editor.py               (later)
```

A specialist gets its own folder only when it outgrows one file. Content types shared by all
specialists and the editor live in `studio/models.py`.

### 4.3 Shared building blocks

`Base` is database infrastructure every feature inherits from, so it lives in `core/db.py`,
not in `auth/`. `get_current_user` is an auth concern, so it lives in `auth/deps.py`.
`Annotated` aliases remove repeated `Depends(...)` boilerplate from every route.

```python
# core/db.py
class Base(DeclarativeBase):
    pass

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auth/deps.py
async def get_current_user(request: Request, db: DbSession) -> User: ...

CurrentUser = Annotated[User, Depends(get_current_user)]

# any router
@router.get("/history")
async def list_history(user: CurrentUser, db: DbSession) -> HistoryList: ...
```

### 4.4 Tests

```
backend/
  tests/                     deterministic; `uv run pytest`
    conftest.py  fakes.py  factories.py
    core/ auth/ profile/ connections/ insights/ history/ trends/ earn/ subscriptions/ admin/
    agents/  supervisor/ research/ studio/ llm/ runtime/
    security/                app-wide rules only (e.g. every route requires login)
  evals/                     real LLMs, scored; `uv run pytest evals` (see evals/README.md)
```

- **Folder = what is tested.** Folders mirror `app/`; a folder is created with its first test.
- **Marker = what the test needs:** `db` (Postgres), `integration` (network + API keys).
  The default run skips `integration` and finishes in seconds. CI runs the default set.
- **Security:** rules for one feature (token checks, ownership, OAuth state) live in that
  feature's folder; `tests/security/` holds rules across the whole app (route auth, no
  secrets in errors or logs, CORS, untrusted web content, internal-address fetch guard).
- **Fakes are passed in, not patched:** constructor arguments (`ResearchAgent(llm=FakeLLM())`)
  and FastAPI `dependency_overrides`. HTTP to external services is faked with `respx`.
- **Evals are not tests:** see D19 and `backend/evals/README.md`.

### 4.5 Daily commands (from `backend/`, no venv activation)

| Task                       | Command                                            |
| -------------------------- | -------------------------------------------------- |
| Install / sync environment | `uv sync`                                          |
| Run tests                  | `uv run pytest`                                    |
| Format                     | `uv run ruff format .`                             |
| Lint (and auto-fix)        | `uv run ruff check . --fix`                        |
| Type check                 | `uv run pyright`                                   |
| Start the API              | `uv run uvicorn app.main:app --reload --port 8000` |
| Migrate the database       | `uv run alembic upgrade head`                      |
| Add or upgrade a package   | `uv add <package>==<version>` (dev: `--dev`)       |
| Remove a package           | `uv remove <package>`                              |

---

## 5. Key designs

### 5.1 Run pool (`agents/state.py`)

```python
class RunState(TypedDict, total=False):
    # Inputs: written once at start, read by everyone
    request: RunRequest
    profile: CreatorProfile
    voice: VoiceSpec                       # from TONE_TO_VOICE

    # Shared decisions: one owner each, read-only for everyone else
    plan: RunPlan                          # owner: supervisor
    research: ResearchPack                 # owner: research
    brief: CreativeBrief                   # owner: director

    # Outputs: written in parallel, merged by reducers
    pieces: Annotated[list[ContentPiece], operator.add]
    issues: Annotated[list[Issue], operator.add]
```

Rules:

1. One owner per key — enforced by a test that fails if a step writes a key it does not own.
2. Decisions do not change once written. A specialist that disagrees with the brief reports an `Issue`.
3. Large things by reference: media in storage, the pool holds URLs.
4. Everything typed, so a bad write fails at the step that made it.

Each specialist receives only its slice of the pool through LangGraph `Send`:

```python
def assign(state: RunState) -> list[Send]:
    return [
        Send(registry[a.deliverable].specialist,
             {"assignment": a, "brief": state["brief"], "voice": state["voice"]})
        for a in state["brief"].assignments
    ]
```

### 5.2 Supervisor (`agents/supervisor/`)

The first step of every run. It replaces the old keyword supervisor (which blocks normal
prompts such as "5 ways to kill procrastination") and makes **no LLM calls** (D16): every
check is deterministic, instant and free. The folder will grow in later versions (D15).

- Input checks: empty or oversized prompt, unsupported options.
- Limits: plan quota (`subscriptions/policy.py`), per-user rate limit.
- Run plan built from the request itself: deliverables from the chosen platform and content
  type; research on by default.

```python
class RunPlan(ContractModel):
    verdict: Literal["allow", "block"]
    reason: str | None = None              # shown to the user when blocked
    needs_research: bool = True
    deliverables: list[DeliverableKey]     # from platform + content type in the request
```

Content safety moves into an LLM call that happens anyway — see Open questions.

### 5.3 Research (`agents/research/`)

- Ported from `D:\cupid_agents\web-search-agent` with its test suite (311 tests).
- API keys come from Cupid `settings`; tuning values stay in its own frozen `config.py`.
- `adapter.py`: Cupid profile → `PersonaContext`; `ResearchResult` → `ResearchPack`
  (sources with ids, titles and URLs, plus their documents).
- No compression yet (D8). In Phase 6 the pack's documents become selected passages; the
  director's input shape stays the same.
- Status handling: `COMPLETE` → continue. `LOW_COVERAGE` / `TIMEOUT` with sources → continue,
  marked degraded for the user. `FAILED` → see Open questions.

### 5.4 Studio (`agents/studio/`)

Typed, addressable content (D10), so the editor can later target "paragraph 2" or "the image
on slide 3":

```python
class TextBlock(ContractModel):
    kind: Literal["text"] = "text"
    role: str | None = None               # "hook", "body", "cta", "hashtags", ...
    text: str

Block = Annotated[TextBlock, Field(discriminator="kind")]   # later: ImageBlock | SlideBlock | SceneBlock

class ContentPiece(ContractModel):
    id: str
    deliverable: str                      # "linkedin_post", "x_thread", "carousel", ...
    variant: int
    blocks: list[Block]
    source_ids: list[str]
    status: Literal["ready", "degraded", "failed"]
```

- **Director:** one call with the strongest available model. Writes the `CreativeBrief`:
  core message, audience insight, facts (each with a source id), style guide, visual
  direction, and one assignment (angle, hook, outline) per deliverable variant.
- **Registry:** a new format is a new `FormatSpec`, not new graph code.

  ```python
  @dataclass(frozen=True)
  class FormatSpec:
      key: str                                  # "linkedin_post"
      specialist: str                           # "writer"
      model_role: str                           # resolved by the gateway
      max_chars: int | None
      guide: str                                # what a great one looks like
  ```

- **Specialists** share one interface, so the director routes through the registry:
  `async def make(task: Assignment, brief: CreativeBrief) -> ContentPiece`.
  (`edit()` is added with the editor.)
- **Reviewer:** code checks (length limits, hashtags, banned phrases, every number traceable
  to a fact) plus one judge call; at most one rewrite per piece.
- **Voices:** `TONE_TO_VOICE` lives only in `voices.py`, covers every `Tone`, and a test fails
  when a tone has no voice.

### 5.5 LLM gateway (`agents/llm/`)

Built by promoting the research agent's `LLMClient` (and its tests), not written from scratch.

- **Roles → provider lists** in settings: `research`, `director`, `writer`, `judge`,
  later `image`, `video`. Switching a model is a config change.
- **One provider per role per run** (D5): chosen at run start, kept for the run, so prompt
  caches hit and voice stays consistent. Rotate across runs, never within one.
- **Rate limits:** on HTTP 429, mark the provider cooling down until its reset time and use
  the next one in the list.
- **Calls:** timeout per role, retry only retryable errors, structured output (JSON schema →
  Pydantic), provider privacy options where supported (D6).
- **Prompt order for caching (D7)** — most shared first:

  ```
  [role instructions]   same for every user and run
  [creator profile]     same for this user
  [run block]           voice, brief (research for the director) — same for every call in the run
  [task]                the only part that changes per call
  ```

  One function renders prompts; no timestamps, ids or random ordering in the shared part.
  Tests: rendering twice gives identical text; two tasks share the same prefix.
- **Measure:** log tokens per call, including `usage.prompt_tokens_details.cached_tokens`;
  report cache hit rate per role.

### 5.6 Runtime (`agents/runtime/`)

- **Checkpointer:** `langgraph-checkpoint-postgres` (needs psycopg 3 next to asyncpg),
  `durability="sync"`, thread id = run id. Checkpoints are deleted after finalize.
- **Start and resume are one function:**

  ```python
  async def execute(run_id: str, request: RunRequest | None = None) -> None:
      config = {"configurable": {"thread_id": run_id}}
      payload = initial_state(request) if request else None   # None = resume from last checkpoint
      async for mode, chunk in graph.astream(
          payload, config, stream_mode=["updates", "custom"], durability="sync"
      ):
          await events.publish(run_id, to_event(mode, chunk))
  ```

- **Worker:** runs execute outside the API process (SAQ on Redis), so deploys and restarts
  do not kill runs; the worker's concurrency limit protects provider rate limits.
- **Events:** Redis stream per run → SSE. Reconnects resume from `Last-Event-ID`.
  Types: `run.started`, `step.started`, `step.finished`, `research.sources`, `piece.ready`,
  `run.degraded`, `run.failed`, `run.completed`.
- **Endpoints** (all under v1, D1):

  | Method | Path                                  | Status                 |
  | ------ | ------------------------------------- | ---------------------- |
  | POST   | `/api/v1/agents/generate`             | exists, body unchanged |
  | GET    | `/api/v1/agents/runs/{id}`            | exists (snapshot)      |
  | GET    | `/api/v1/agents/runs/{id}/events`     | new (SSE)              |
  | POST   | `/api/v1/agents/runs/{id}/resume`     | new                    |

- **Failure handling:**

  | Failure                              | Handling                                                    |
  | ------------------------------------ | ----------------------------------------------------------- |
  | Rate limit, timeout, 5xx on a call   | Gateway retries, then the next provider for that role       |
  | A step keeps failing                 | `RetryPolicy(max_attempts=2)`, then run marked failed, resumable |
  | Worker crash or deploy               | Queue hands the job out again → `execute(run_id)` resumes   |
  | User clicks Retry                    | `POST .../resume` → `execute(run_id)`                       |
  | Weaker result                        | Run completes with a visible "degraded" label               |

- **Resume safety:** side effects only in finalize, keyed by run id. Slow media jobs store
  the provider's job id in state before waiting, so a resume never pays twice.

### 5.7 Error handling

1. Catch only where you can act: retry, fall back, or translate. Otherwise let it propagate.
2. Services raise typed `AppError`s; one handler turns them into HTTP. Routers have no try/except.
3. Agents return expected outcomes as typed statuses; exceptions mean unexpected → the runtime
   marks the run failed and resumable.
4. Log once, where the error is handled.

```python
# core/errors.py
class AppError(Exception):
    status: int = 500
    code: str = "internal_error"

class NotFoundError(AppError):  status, code = 404, "not_found"
class ForbiddenError(AppError): status, code = 403, "forbidden"
class ConflictError(AppError):  status, code = 409, "conflict"

# main.py — the only place errors become HTTP
@app.exception_handler(AppError)
async def app_error(_, exc: AppError) -> JSONResponse:
    return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status)
```

LLM provider errors (retryable, rate-limited, permanent, circuit-open) come from the research
agent's provider module and become `agents/llm/errors.py`. Existing features keep
`HTTPException` until they are next touched; new code uses `AppError`.

---

## 6. Phases

Each phase ends with the whole app working, including its own small UI piece. Phases are
ordered by dependency: new code lands in its final place (Phase 1), the gateway exists before
research is ported onto it (Phase 2), and Phase 2's placeholder supervisor runs basic input
checks until the full supervisor lands (Phase 4).

### Phase 0 — Stabilize (S)

- [x] Restore `models/top_content.py`.
- [x] Baseline commit of the old codebase (`db5fd4e`).
- [x] Switch to uv (D17): dependencies in `pyproject.toml` (direct pins, dev group) with
      `uv.lock`; `requirements*.txt` removed; local `.venv` synced (unused packages such as
      torch removed). Verified: app starts, same test results as before.
- [x] Tests: `integration` and `db` markers (strict); default run skips `integration`; the
      3 network tests marked; 6 keyword-supervisor and 2 trends failures are strict xfails.
      Default run: ~1 s, green.
- [x] Removed settings nothing reads (ChromaDB, Ollama, Reddit, Resend, Anthropic, Gemini)
      and the ChromaDB container; `.env.example` lists exactly the settings, enforced by a test.
- [x] Request options (content type, platform, length, tone) defined once per language:
      `app/agents/models.py` and `frontend/lib/api.ts`, kept equal by a test.
- [x] CI backend job uses uv (`setup-uv`, `uv sync --locked`) and runs ruff and pytest.
- [x] CI green locally: Prettier applied, 0 ESLint errors (17 warnings remain), tsc and
      `next build` pass, `npm ci` accepts the lock file, no Linux path-case problems.
- [x] `backend/Scripts/` tracked as `scripts/` (Linux CI is case-sensitive).
- [x] Stopped tracking generated `next-env.d.ts` and `tsconfig.tsbuildinfo`.
- [x] Tag `legacy-pipeline` on the baseline commit (`db5fd4e`).
- [x] Removed pre-commit hooks (D18); pyright replaces mypy as the type checker.
- [ ] Fix pyright errors in code that stays (40 as of Phase 1, incl. 6 in scripts/; ~15 in old agents/trends that are
      deleted later, ~7 real `None`-handling gaps, ~13 library typing noise), then add
      `uv run pyright` to CI.
- [x] Pushed the `phase-0-stabilize` branch and the `legacy-pipeline` tag; CI green, merged into `main` (PR #2).

Done when: the app starts, `pytest` passes in seconds, CI is green on GitHub.

### Phase 1 — Reorganize (M)

Pure moves, no behavior change. One commit per feature, using `git mv` to keep history.

- [x] Before moving: snapshot of the OpenAPI schema, every table definition and test results.
- [x] `core/`: `Base` and `DbSession` in `db.py`; `tables.py` discovers every `models.py`
      automatically (no list to keep in sync, so no test needed); `errors.py` with one JSON
      handler in `main.py` (tested); `oauth_state.py` moved in.
- [x] `auth/`: models, schemas, service, `google.py` (OAuth client), `session.py` (JWT +
      session cookie), `deps.py` (`get_current_user`, `CurrentUser`), `router.py` (both auth
      routers merged; URLs unchanged).
- [x] `profile/`, `connections/`, `history/`, `admin/` (AuditLog), `agents/router.py` +
      `agents/schemas.py`.
- [x] `insights/`: one `models.py` for both tables (snapshot + top content).
- [x] `trends/`: models, schemas, router; the dead Celery task (`tasks/trends_ingest.py`) deleted.
- [x] `alembic/env.py` uses `core.tables`; `tests/conftest.py` imports `Base` from `core/db.py`.
- [x] Emptied `models/`, `schemas/`, `services/`, `routers/`, `tasks/` deleted.
- [x] Tests mirror the app: `tests/<feature>/`.
- [x] Stale `pyrightconfig.json` (it silently overrode `pyproject.toml`) and an empty
      `backend/package-lock.json` removed.
- [x] README project tree updated.
- [x] Pushed, CI green, merged into `main` (PR #3).

Done when: the OpenAPI schema is identical, `alembic revision --autogenerate` produces an
empty migration, test results are unchanged, and the app starts.

Result: OpenAPI schema and all 11 table definitions identical (compared directly, since
Docker was off for autogenerate); tests unchanged; the app starts and serves its routes.

### Phase 1.5 — Test foundation (S)

- [x] Ruff security rules (`S`) on; 6 false alarms marked inline with reasons.
- [x] `tests/security/` with the first app-wide rule: every route requires login except an
      allowlist of 5 deliberately public routes (verified it catches a forgotten check).
- [x] `tests/agents/supervisor/` subfolder; `backend/evals/` skeleton with its README.
- [x] `conftest.py` rewritten: one event loop per run, working Postgres fixtures
      (`db_session` rolled back per test, auto `db` marker, skip locally / fail in CI when
      the DB is down), `db_client`, `sign_in(user)`; trends fixtures moved to its conftest.
- [x] `factories.py` (`make_user`, `make_history`, `make_subscription`, `save`).
      `FakeLLM` / `fakes.py` deferred to Phase 2 so it matches the gateway's interface.
- [x] Dev tools: `respx`, `pytest-cov` (baseline coverage 52%).
- [x] CI: Postgres service (`db` tests run), coverage, `pip-audit`, vitest, `npm audit`
      (production deps), gitleaks secret scan over full history (`.gitleaksignore`).
- [x] Tests: session cookie checks, entitlement rules, history ownership (25 tests).
- [x] App-wide security tests: no secrets in settings output/errors or 500 responses,
      CORS origin. Fetch-guard and untrusted-content tests deferred to Phase 3 (research).
- [x] Fixed what the new checks found: settings leaked secrets (now hidden); 7 vulnerable
      Python packages (upgraded; python-jose replaced by PyJWT, existing sessions stay
      valid); 22 frontend vulnerabilities (production audit now 0); Phase 1's
      `alembic check` confirmed against the real DB.
- [x] `backend/tests/tests.md`: guide to the test suite.
- [ ] **Revoke the Hugging Face token** found in git history (repo is public) —
      huggingface.co/settings/tokens. Owner action.

Done when: DB tests run in CI, and auth, entitlements and history ownership are covered.

### Phase 2 — Agent foundations (L)

Test-first, on placeholder steps.

- [ ] `agents/models.py` (shared contracts) and `state.py` (run pool) with the ownership test.
- [ ] `llm/`: gateway from the research `LLMClient` and its tests; roles from settings; one
      provider per run; 429 cooldown; timeouts; structured output; usage and cached-token
      logging; privacy options; prompt builder with determinism tests.
- [ ] `runtime/`: Postgres checkpointer, `execute()`, events, SSE endpoint, SAQ worker,
      `resume` endpoint.
- [ ] Placeholder supervisor, research and studio steps.
- [ ] UI: create page switches from polling to live events and shows step progress.

Done when: a placeholder pipeline runs through the API; the crash test passes (break step 2,
resume, step 1 does not re-run); prompt-prefix tests pass.

### Phase 3 — Research (M)

- [ ] Port the agent and its 311 tests into `agents/research/` and `tests/agents/research/`,
      using the gateway and Cupid settings.
- [ ] `adapter.py`: profile → `PersonaContext`; result → `ResearchPack`.
- [ ] Delete the old personalization and research packages and their tests; drop `ddgs`,
      `langsmith` and other packages only they used.
- [ ] UI: sources panel fed by `research.sources` events.

Done when: the 311 tests pass in Cupid CI and a real run shows research progress and sources live.

### Phase 4 — Supervisor (S)

- [ ] Deterministic supervisor: input checks, quota and rate limits, `RunPlan` from the request.
- [ ] Content safety in the agreed place (see Open questions), tested with about 40 prompts,
      including normal ones the keyword supervisor blocked.
- [ ] Replace the old keyword supervisor and its tests.
- [ ] UI: blocked-reason message.

Done when: the 40-prompt test set passes with no extra LLM calls.

### Phase 5 — Studio, text (L)

- [ ] `studio/models.py` (blocks, `ContentPiece`, `CreativeBrief`), `voices.py`, `registry.py`,
      `director.py`, `specialists/writer.py`, `reviewer.py`.
- [ ] History stores `ContentPiece`s (migration from the old variants shape).
- [ ] Test set of 20–30 real prompts with a judge rubric.
- [ ] Delete the old composer, old `graph.py`, `state.py`, `run_store.py`; drop
      `langchain-core`, `langchain-groq` if unused.
- [ ] UI: render blocks; edits save back to history.
- [ ] README: rewrite the architecture section for the new pipeline (it still describes the
      old agents and `MemoryState`).

Done when: the studio beats the old composer on the test set and no old agent code remains.

### Phase 6 — Optimize (M)

- [ ] Research compression: select passages per source, tuned by a fact-survival test on
      saved runs.
- [ ] Cache tuning from logged `cached_tokens`; stagger parallel calls only if data says so.
- [ ] Tokens and time per run; load test against free-tier limits.

Done when: agreed latency and token targets are met.

### Phase 7+ — Expand

- [ ] Designer (images), infographic, animator and video specialists — one at a time.
- [ ] Editor: `edit()` on specialists, targeting single blocks.
- [ ] Trends rebuild (D14).
- [ ] Memory across runs (learn a creator's voice from approved posts).

---

## 7. Open questions

- **Research fails completely:** write without research and say so in the UI, or fail the run?
- **Launch deliverables:** which formats ship first (e.g. LinkedIn post, X thread, carousel)?
- **Targets:** maximum time to first draft; maximum tokens per run.
- **Content safety without a supervisor LLM call (D16):** recommended — add `allowed` and
  `reason` fields to the structured output of an LLM call that already happens (the research
  planner, or the director when research is off): zero extra calls. Alternative: rely only on
  providers' built-in refusals.

---

## 8. Later

- Paid provider tiers at launch (free tiers cap throughput).
- Frontend types generated from the OpenAPI schema instead of hand-written.
- Tracing dashboard (e.g. Langfuse) once logged usage is not enough.
- Consider PyJWT in place of python-jose for session tokens.
- Clear the 17 ESLint warnings (mostly unused variables) as those files are touched.
- Adopt `eslint-plugin-react-hooks` 7.1 (pinned to 7.0.1 via npm overrides): its stricter
  rules report 8 findings, some possibly real bugs ("variable used before declared").
