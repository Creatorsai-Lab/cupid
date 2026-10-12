# Backend tests

How Cupid's backend is tested: what each kind of test is for, where it goes, how to
write one, and what is still missing. Decisions behind this are D19 and D20 in
`dev_resources/updated_version_plan.md`.

---

## 1. Quick start

Run everything from `backend/`. No virtual environment to activate — `uv run` uses
`backend/.venv` (created by `uv sync`).

| Task                                        | Command                                      |
| ------------------------------------------- | -------------------------------------------- |
| Default suite (fast, offline; what CI runs) | `uv run pytest`                              |
| One folder / file / test                    | `uv run pytest tests/auth`                   |
|                                             | `uv run pytest tests/auth/test_session_token.py` |
|                                             | `uv run pytest -k callback`                  |
| Tests that need Postgres                    | `uv run pytest -m db` (start Docker first)   |
| Tests that call real APIs (keys + network)  | `uv run pytest -m integration`               |
| Evals (real LLMs, scored — not tests)       | `uv run pytest evals` (see `evals/README.md`) |
| Lint, format, types                         | `uv run ruff check .` · `uv run ruff format .` · `uv run pyright` |

The default suite must stay **fast (seconds) and offline**. If a test needs the network
or a real API key, it is not a default test — mark it `integration`.

---

## 2. Tests vs evals

|          | `tests/` (this folder)                | `evals/`                                 |
| -------- | ------------------------------------- | ---------------------------------------- |
| Question | Is our code correct?                  | Is the agents' output good?              |
| LLM      | Fakes only (`FakeLLM`), never real    | Real providers, never fakes              |
| Result   | Pass/fail, identical every run        | Scores vs thresholds, varies per run     |
| Runs     | Every change and in CI                | By hand, before a prompt or model change |

A test that calls a real LLM is flaky and costs money; an eval that uses a fake LLM
only tests the fake. Keep them apart.

---

## 3. Layout

```
backend/tests/
  conftest.py              shared fixtures (see section 6)
  tests.md                 this file
  core/                    settings, errors, DB plumbing
  auth/                    sign-in, session token, cookie
  connections/             YouTube OAuth connection
  trends/                  trending articles
  agents/                  request options, old pipeline (integration)
    supervisor/            one subfolder per agent part:
                           later research/, studio/, llm/, runtime/
  security/                rules that apply across the whole app
```

Not yet tested (folders appear with their first test): `profile/`, `insights/`,
`history/`, `earn/`, `subscriptions/`, `admin/`.

### The two rules

1. **Folder = what is tested.** Folders mirror `app/`: a test for `app/history/service.py`
   goes in `tests/history/`. Agents get one subfolder per part (`tests/agents/studio/`).
2. **Marker = what the test needs.** Never make a folder for a kind of test.

| Marker               | Needs                    | Runs by default?                      |
| -------------------- | ------------------------ | ------------------------------------- |
| *(none)*             | nothing external         | yes                                   |
| `@pytest.mark.db`    | the Postgres test DB     | yes, once DB fixtures work (see §8)   |
| `@pytest.mark.integration` | network + API keys | no — `uv run pytest -m integration` |

Markers are strict (`--strict-markers`): a typo in a marker name is an error. They are
declared in `pyproject.toml` under `[tool.pytest.ini_options]`.

### Where security tests go

- **One feature's rule → that feature's folder.** Examples: a forged token is rejected
  (`auth/`), you can't read another user's history (`history/`), a forged OAuth state is
  rejected (`connections/`).
- **A rule for the whole app → `security/`.** Examples: every route requires login unless
  allowlisted (exists: `security/test_route_auth.py`), no secrets in error messages or
  logs, CORS allows only the frontend, agents don't obey instructions inside fetched web
  pages, the page fetcher refuses internal addresses.

If you add a deliberately **public** route, add it to `PUBLIC_ROUTES` in
`security/test_route_auth.py` with the reason — otherwise that test fails, by design.

---

## 4. Writing a test

1. **One behavior per test, named after it.** `test_callback_rejects_unverified_email`,
   not `test_callback_2`.
2. **Pass fakes in; don't patch internals.** Give the code its dependencies:
   - agents and clients take them in the constructor:
     `ResearchAgent(llm=FakeLLM(...), search=FakeSearch(...))`
   - routes take them through FastAPI: `app.dependency_overrides[get_current_user] = ...`

   `monkeypatch` on module internals breaks whenever code moves; use it only for
   environment variables.
3. **Fakes record what they received,** so tests can check the prompt or request that
   was sent, not only the result (e.g. `fake_llm.calls[-1]["user"]`).
4. **No real network.** External HTTP goes through `httpx`; fake it with `respx`
   (planned, §8). A test that reaches the internet must be marked `integration`.
5. **Time is an input.** Pass `now=` / a clock function instead of patching the clock
   (the research agent already does this).
6. **Expected failures are explicit.** Known-wrong behavior that will be replaced is
   marked `pytest.mark.xfail(reason=..., strict=True)` — strict, so if it starts passing
   the run fails and someone removes the marker.
7. **Async tests need no decorator** (`asyncio_mode = "auto"`): just `async def test_...`.

Example: an API test with a fake signed-in user (pattern; the shared fixture is planned):

```python
from app.auth.deps import get_current_user
from app.main import app


async def test_history_requires_owner(client, make_user):
    app.dependency_overrides[get_current_user] = lambda: make_user()
    try:
        response = await client.get("/api/v1/history/")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

---

## 5. Testing agents

Agent tests are deterministic: every LLM call goes to a `FakeLLM` that returns queued
answers. Quality of real output belongs in `evals/`.

- **One step:** call the step directly with a state dict and a `FakeLLM`.
- **Whole pipeline:** compile the graph with a fresh `InMemorySaver` per test.
- **A section of the pipeline / resume:** set state with
  `graph.update_state(config, values, as_node="research")`, then run with
  `graph.invoke(None, config, interrupt_after=...)`.
- **Must-have tests for the runtime (Phase 2):** break step 2, resume, and assert step 1
  did not run again; the first part of every prompt is identical between calls (needed
  for prompt caching); each step writes only the state fields it owns.
- The research agent arrives with 311 tests using `FakeLLM` (Phase 3); they move to
  `tests/agents/research/`.

---

## 6. Fixtures available today (`conftest.py`)

| Fixture                | What it gives                                   | Status                 |
| ---------------------- | ----------------------------------------------- | ---------------------- |
| `client`               | `httpx.AsyncClient` talking to the app in-process | works                |
| `engine`, `db_session` | Postgres test DB, rolled back after each test   | not working yet (§8)   |
| `sample_persona`, `sample_persona_empty` | persona dicts for the trends ranker | works; moves to `trends/conftest.py` |

Put fixtures used by one feature in that feature's own `conftest.py`; only shared
fixtures belong in the top-level one.

---

## 7. CI

`.github/workflows/ci.yml` runs on every pull request and push to `main`:
`uv sync --locked`, `ruff check`, `ruff format --check`, `pytest` (default suite, with a
test-only `SECRET_KEY` so settings load without `.env`). Evals and `integration` tests
never run in CI.

Ruff's security rules (`S`, from bandit) are on. In `tests/` and `evals/`, `assert` and
fake credentials are allowed. Anywhere else, a false alarm is silenced inline **with its
reason**, e.g. `# noqa: S311 - retry jitter, not security`.

---

## 8. Current state and what's next

As of 2026-10-12: **78 passed, 8 expected failures, 2 skipped, 5 integration
(deselected)**, in about a second.

Known expected failures (strict `xfail`):
- 6 in `agents/supervisor/` — the keyword supervisor misjudges intent; it is replaced in
  Phase 4.
- 2 in `trends/` — authority scores drifted; trends is rebuilt later.

Still to do (Phase 1.5 in the plan):
- [ ] `conftest.py`: remove the old custom `event_loop` fixture, make `db_session` work
      against Postgres, move `sample_persona` into `trends/conftest.py`.
- [ ] `fakes.py` (`FakeLLM`, …), `factories.py` (`make_user()`, `make_profile()`, …),
      and a shared fake signed-in user fixture.
- [ ] Add `respx` (fake HTTP) and `pytest-cov` (coverage report) to the dev group.
- [ ] CI: Postgres service so `db` tests run; `pip-audit`, `npm audit`, secret scan.
- [ ] Tests for auth, entitlements (money rules) and history ownership.
- [ ] More `security/` tests: no secrets in errors/logs, CORS origin, internal-address
      fetch guard.

Coverage is reported, not enforced as a percentage. What is enforced: auth, money
(entitlements), ownership checks and agent resume always have tests.
