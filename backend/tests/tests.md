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
  factories.py             make_user(), make_history(), make_subscription(), save()
  tests.md                 this file
  core/                    settings, errors
  auth/                    sign-in, session token and cookie, current user
  connections/             YouTube OAuth connection
  history/                 ownership of saved creations
  subscriptions/           entitlement rules (what each plan grants)
  trends/                  trending articles (+ its own conftest.py)
  agents/                  request options; one subfolder per agent part
                           (supervisor/, research/, studio/, llm/, runtime/ as they land)
    legacy/                old pipeline's tests; deleted with the old pipeline
  security/                rules that apply across the whole app
```

Not yet tested (folders appear with their first test): `profile/`, `insights/`,
`earn/`, `admin/`.

### The two rules

1. **Folder = what is tested.** Folders mirror `app/`: a test for `app/history/service.py`
   goes in `tests/history/`. Agents get one subfolder per part (`tests/agents/studio/`).
2. **Marker = what the test needs.** Never make a folder for a kind of test.

| Marker               | Needs                    | Runs by default?                      |
| -------------------- | ------------------------ | ------------------------------------- |
| *(none)*             | nothing external         | yes                                   |
| `@pytest.mark.db`    | the Postgres test DB     | yes — **added automatically** to any test using `db_session` |
| `@pytest.mark.integration` | network + API keys | no — `uv run pytest -m integration` |

Markers are strict (`--strict-markers`): a typo in a marker name is an error. They are
declared in `pyproject.toml` under `[tool.pytest.ini_options]`.

### Where security tests go

- **One feature's rule → that feature's folder.** Examples: a forged token is rejected
  (`auth/`), you can't read another user's history (`history/`), a forged OAuth state is
  rejected (`connections/`).
- **A rule for the whole app → `security/`.** Today:
  - `test_route_auth.py` — every route requires login unless allowlisted;
  - `test_no_secret_leaks.py` — settings never print secrets, settings errors never
    echo input, unhandled 500s never reveal exception details;
  - `test_cors.py` — only the frontend origin may call the API with credentials.

  Coming with the agents: fetched web pages can't instruct the agents, and the page
  fetcher refuses internal addresses (Phase 3).

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
   (`respx.mock` + a route per URL). A test that reaches the internet must be marked
   `integration`.
5. **Time is an input.** Pass `now=` / a clock function instead of patching the clock
   (the research agent already does this).
6. **Expected failures are explicit.** Known-wrong behavior that will be replaced is
   marked `pytest.mark.xfail(reason=..., strict=True)` — strict, so if it starts passing
   the run fails and someone removes the marker.
7. **Async tests need no decorator** (`asyncio_mode = "auto"`): just `async def test_...`.

Example: an API test against the database, as a signed-in user
(from `history/test_ownership.py`):

```python
from tests.factories import make_history, make_user, save


async def test_cannot_delete_another_users_entry(db_client, db_session, sign_in):
    me, other = make_user(), make_user()
    theirs = make_history(other)
    await save(db_session, me, other, theirs)
    sign_in(me)

    response = await db_client.delete(f"/api/v1/history/{theirs.id}")

    assert response.status_code == 404
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

## 6. Fixtures and helpers

| Name                   | What it gives                                                     |
| ---------------------- | ----------------------------------------------------------------- |
| `client`               | `httpx.AsyncClient` talking to the app in-process (no DB)         |
| `db_session`           | Postgres session inside a transaction rolled back after the test; the code's own `commit()` calls become savepoints. Using it marks the test `db`. |
| `db_client`            | `client` whose requests use `db_session`                          |
| `sign_in(user)`        | requests act as `user` (skips the cookie check)                   |
| `engine`               | session-wide engine; creates the schema once per run from the models |
| `tests/factories.py`   | `make_user()`, `make_history(user)`, `make_subscription()` — defaults, override any field; `save(session, *objs)` adds and flushes |

Dependency overrides (`sign_in`, `db_client`) are reset after every test automatically.

**Database tests locally:** start Postgres with `docker compose up -d` (from the repo
root). The test database is `cupid_test_db` (override with `TEST_DATABASE_URL`). If
Postgres isn't running, `db` tests are **skipped** with that hint; in CI they **fail**
instead, so they can never be silently skipped there.

Put fixtures used by one feature in that feature's own `conftest.py`; only shared
fixtures belong in the top-level one.

---

## 7. CI

`.github/workflows/ci.yml` runs on every pull request and push to `main`:

| Job      | Checks                                                                 |
| -------- | ---------------------------------------------------------------------- |
| backend  | `uv sync --locked`, ruff (incl. security rules), `pytest` with coverage against a Postgres service, `pip-audit` (known vulnerabilities in any locked package fail) |
| frontend | `npm ci`, Prettier, ESLint, `tsc`, vitest, `npm audit` on production dependencies (high+ fails), `next build` |
| secrets  | gitleaks over the full git history; reviewed historical findings are listed in `.gitleaksignore` with reasons, anything new fails |

Evals and `integration` tests never run in CI.

Ruff's security rules (`S`, from bandit) are on. In `tests/` and `evals/`, `assert` and
fake credentials are allowed. Anywhere else, a false alarm is silenced inline **with its
reason**, e.g. `# noqa: S311 - retry jitter, not security`. A fake secret in a test is
marked `# gitleaks:allow`.

---

## 8. Current state and what's next

As of 2026-10-12: **110 passed** (10 of them against Postgres), **8 expected failures**,
2 skipped, 5 integration deselected. Coverage of `app/`: **52%**
(`uv run pytest --cov=app`).

Known expected failures (strict `xfail`):
- 6 in `agents/legacy/supervisor/` — the keyword supervisor misjudges intent; it is replaced in
  Phase 4.
- 2 in `trends/` — authority scores drifted; trends is rebuilt later.

Next:
- `FakeLLM` in a shared `fakes.py` arrives with the LLM gateway (Phase 2), so it matches
  the gateway's interface; the research agent's 311 tests come in Phase 3.
- Security tests for fetched web content and internal-address fetching come with the
  research agent (Phase 3).
- `profile/`, `insights/`, `earn/`, `admin/` get tests when their code is next touched.

Coverage is reported, not enforced as a percentage. What is enforced: auth, money
(entitlements), ownership checks and agent resume always have tests.
