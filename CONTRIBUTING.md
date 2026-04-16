# Contributing to Cupid

Thank you for your interest in contributing. Cupid is built to production-grade standards from day one. This document defines the exact workflow, commit conventions, code standards, and review criteria that all contributors — including the core maintainer — must follow.

These standards are directly inspired by the engineering practices of Anthropic, Google DeepMind, and OpenAI. Consistency and clarity in every contribution makes the codebase maintainable, reviewable, and trustworthy at scale.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Before You Contribute](#before-you-contribute)
- [Development Environment](#development-environment)
- [Branch Strategy](#branch-strategy)
- [Commit Message Standard](#commit-message-standard)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Requirements](#documentation-requirements)
- [What We Will Not Merge](#what-we-will-not-merge)

---

## Code of Conduct

All contributors are expected to engage professionally and respectfully. Criticism must be directed at ideas and code, never at people. Contributions that include discriminatory language, harassment, or bad-faith engagement will be closed without discussion.

---

## Before You Contribute

### For Bug Reports

Search existing issues before opening a new one. A useful bug report includes:

- A precise description of the observed behavior
- The expected behavior
- Reproduction steps (minimal, numbered, exact)
- Environment details: OS, Python version, Node version, relevant dependency versions
- Logs or error output (full stack trace, not a screenshot)

### For Feature Proposals

Open an issue with the label `proposal` before writing any code. Describe:

- The problem you are solving and evidence that it is real
- The proposed solution at a design level
- Alternatives you considered and why you rejected them
- Whether this fits the V1 scope or belongs in a future version

Features that have not been discussed and agreed upon in an issue will not be reviewed as a pull request.

### For Agent or AI Logic Changes

Any modification to agent prompts, the LangGraph graph topology, RAG retrieval logic, or the personalization fidelity scoring must include:

- A written explanation of why the change improves output quality
- Before/after example outputs demonstrating the improvement
- No regression in existing passing tests

---

## Development Environment

Follow the setup guide in [README.md](./README.md) completely before contributing. Your local environment must have all services running and all tests passing before you open a branch.

Required tools:

- Python 3.11
- Node.js 18+
- Docker Desktop
- Ollama with `llama3.2` and `nomic-embed-text` pulled
- `ruff` installed in your backend virtual environment

---

## Branch Strategy

Cupid uses trunk-based development. All work branches off `main` and merges back to `main` via pull request.

**Branch naming convention:**

```
<type>/<short-description>
```

Types match the commit type tags defined below. Examples:

```
feat/personalization-card-synthesis
fix/chroma-namespace-isolation
chore/update-langgraph-dependency
docs/api-endpoint-reference
refactor/research-agent-react-loop
test/composer-fidelity-scoring
```

Rules:

- Branch names are lowercase with hyphens only. No underscores, no camelCase.
- Branches must be short-lived. A branch that is open for more than 7 days without activity will be closed.
- Do not commit directly to `main`. Ever.

---

## Commit Message Standard

Cupid follows the Conventional Commits specification (v1.0.0), which is the same standard enforced at Google, Anthropic, and most mature open-source projects.

### Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Rules

- The subject line must be 72 characters or fewer
- The subject is written in the imperative present tense: "add", not "added" or "adds"
- No period at the end of the subject line
- The body, if present, explains the *why*, not the *what*
- Breaking changes must include `BREAKING CHANGE:` in the footer

### Commit Types

| Type | When to Use |
|---|---|
| `feat` | A new feature or capability visible to users or the system |
| `fix` | A bug fix |
| `refactor` | Code restructuring with no behavior change and no new feature |
| `perf` | A change that improves performance without changing behavior |
| `test` | Adding or correcting tests only |
| `docs` | Documentation only changes |
| `chore` | Maintenance tasks: dependency updates, config changes, build scripts |
| `ci` | Changes to CI/CD workflows |
| `revert` | Reverting a previous commit |

### Scope (Optional but Encouraged)

Scope refers to the subsystem being changed. Use one of:

`personalization` `research` `trend` `composer` `orchestrator` `analytics` `scheduler` `brand-safety` `notifications` `auth` `api` `db` `frontend` `infra` `agents`

### Examples

```
feat(personalization): add incremental personalization card re-synthesis on new writing sample

fix(composer): correct cosine similarity threshold comparison direction

refactor(trend): extract velocity scoring into standalone pure function

test(research): add unit tests for DuckDuckGo fallback search path

chore: upgrade langgraph to 0.2.x and resolve deprecated StateGraph API

docs(api): document /agents/runs/{run_id} polling contract

feat(auth)!: replace session cookies with HTTP-only JWT

BREAKING CHANGE: all existing sessions are invalidated. Clients must re-authenticate.
```

---

## Pull Request Process

### Before Opening a PR

- All tests must pass locally: `pytest`
- Ruff must report no errors: `ruff check app/`
- Your branch must be rebased on the latest `main`, not merged
- The PR must close or reference an existing issue

### PR Title

The PR title must follow the same format as a commit message subject line:

```
feat(personalization): add hybrid BM25 + dense retrieval to personalization agent
```

### PR Description Template

Every pull request must include:

```
## What this changes
A concise description of the change and its purpose.

## Why
The reasoning. Link to the issue this closes: Closes #<issue-number>

## How to test
Step-by-step instructions for a reviewer to verify correctness manually
if automated tests do not cover the full behavior.

## Checklist
- [ ] Tests written and passing
- [ ] Ruff check passes
- [ ] No new dependencies added without justification in the PR description
- [ ] No secrets, API keys, or personalizationl data in the diff
- [ ] Documentation updated if behavior changed
```

### Review Standards

- PRs require at least one approving review before merge
- Reviewers must read the entire diff, not just the summary
- "LGTM" without comments is not an acceptable review for any change larger than a typo fix
- Reviewers should distinguish between blocking issues and non-blocking suggestions using the prefixes `blocker:` and `nit:` in review comments
- The author is responsible for resolving all blockers. Nits may be addressed at the author's discretion.

### Merge Policy

- Squash merge is used for all PRs. The squash commit message must follow the commit standard above.
- The branch is deleted after merge.
- Do not merge your own PR. If you are the sole maintainer and no reviewer is available, wait 24 hours after opening the PR before self-merging.

---

## Code Standards

### Python (Backend)

- All code must pass `ruff check` with the configuration in `pyproject.toml`
- Format with `ruff format` before committing
- Every function and class must have a docstring. One-liners are acceptable for obvious functions.
- Type annotations are required on all function signatures
- No `print()` statements in application code. Use the logger from `app.core.logging`
- No hardcoded strings for configuration values. All config goes through `app.config.settings`
- Maximum function length is 40 lines. If a function exceeds this, it almost always should be decomposed.
- Agent node functions must be pure with respect to the `MemoryState` — they read from state, return a state update dict, and have no other side effects except logging

### TypeScript (Frontend)

- Strict mode is enabled. No `any` types.
- All API calls go through `lib/api.ts`. No raw `fetch` or `axios` calls in components.
- Components are functional only. No class components.
- State that is local to a component stays in `useState`. State shared across routes goes to Zustand.
- No inline styles. All styling is Tailwind utility classes or CSS variables defined in `globals.css`

### General

- No commented-out code in committed files
- No TODO comments without an associated open issue number: `# TODO(#42): description`
- Secret values never appear in code, logs, or error messages
- New external dependencies require explicit justification in the PR description

---

## Testing Requirements

### Backend

- Every new route must have at least one integration test in `tests/integration/`
- Every agent node must have at least one unit test with a mocked LLM response in `tests/unit/`
- Every non-agent service function (analytics, scheduler, brand safety) must have unit tests with 100% branch coverage
- Tests use `pytest` and `pytest-asyncio`. Fixtures live in `tests/conftest.py`

### Frontend

- Component tests are not required in V1 but are welcome
- API client functions in `lib/api.ts` should have type coverage verified by the TypeScript compiler

### What Makes a Good Test

A good test has one clear assertion per test function, a descriptive name that reads as a sentence (`test_personalization_agent_returns_card_with_required_fields`), and no dependency on external services (mock everything that calls a network or database).

---

## Documentation Requirements

If your change introduces or modifies a public API endpoint, you must update the endpoint docstring in the FastAPI router so that the generated Swagger documentation is accurate.

If your change modifies the LangGraph graph topology (adds a node, changes edge routing, modifies state schema), update the architecture diagram in `docs/architecture.md`.

If your change adds a new required environment variable, add it to both `.env.example` and the environment variables reference table in `README.md`.

---

## What We Will Not Merge

The following will be closed without review:

- PRs that add features not discussed in an issue
- PRs where tests are failing
- PRs that add API keys, credentials, or personalizationl data to the repository
- PRs that bypass the commit message standard without explanation
- PRs that introduce a new LLM API dependency when an existing free or local solution is sufficient for V1
- PRs with PR descriptions that are empty or contain only "fixes bug"
- PRs that reformat large sections of code unrelated to the stated change

---

## Questions

Open a GitHub Discussion rather than an issue for general questions about the codebase, architecture decisions, or contribution process. Issues are reserved for bugs and concrete feature proposals.