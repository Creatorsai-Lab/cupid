## Pyramid of test types (The standard everywhere):
```
┌─────────────────┐
│   E2E tests     │    ← Few. Slow. Test the whole system.
│   (1-5%)        │      Like running the trends API through real HTTP.
├─────────────────┤
│ Integration     │    ← Some. Medium speed. Test multiple components.
│ tests (15-25%)  │      Like ranker + DB working together.
├─────────────────┤
│  Unit tests     │    ← Many. Fast. Test one function in isolation.
│  (70-80%)       │      Like _url_hash returning 32 chars.
└─────────────────┘
```
The pyramid shape is intentional. We want lots of fast unit tests and few slow E2E tests. Why? Because if a unit test fails, wew know exactly which function is broken. If an E2E test fails, the bug could be anywhere.

1. Principle: AAA - Arrange, Act, Assert. Every test follows this shape.
2. Principle: One thing per test. A test asserting five things is bad practice
3. Principle: Test the behavior, not implementation
4. Principle: Tests are for the future-you who forgot how this works. Test names should be sentences. `test_ranker_returns_top_k_only`, `test_url_hash_is_deterministic`. Reading test names should teach someone what the system does.
5. Principle: Fast tests run often, slow tests run never.
6. Principle: Test failures are good news. When a test fails, the test caught a bug before a user did. Treat green tests as the goal, not the absence of failures.
7. Principle: File name must start with `test_` and also function names must start with `test_`

> When Tests Fail:
Read the assertion error message carefully - pytest tells you exactly what value didn't match what was expecte

## Test Infrastructure
Test infrastructure is the plumbing that makes writing tests fast and consistent. Think of it like this:
1. _Without infrastructure:_
    - Each test file → manually creates DB connection → manually creates user
                 → manually generates JWT → manually sets up cleanup
    - Result: 50 lines of setup per test file. Inconsistent. Slow.

2.  With infrastructure:
    - conftest.py defines fixtures: db_session, test_user, authenticated_client
    - Each test file → just uses the fixtures
    - Result: 3 lines of setup per test file. Consistent. Fast.

### Create the test database

Tests run against a separate Postgres database — never your dev DB.
```powershell
docker exec -it cupid_postgres psql -U cupid -d cupid_db -c "CREATE DATABASE cupid_test_db OWNER cupid;"
```
**Verify:**
```powershell
docker exec -it cupid_postgres psql -U cupid -l
```
Should get both `cupid_db` and `cupid_test_db`.

### Testing Commands:
```
# Run everything
pytest
```

```
# Verbose — see each test name
pytest -v
```

```
# Just one folder
pytest tests/unit
```

```
# Just one file
pytest tests/unit/test_ranker.py
```

```
# Tests matching a name pattern
pytest -k "ranker"
```

```
# Stop on first failure
pytest -x
```

```
# Show coverage
pytest --cov=app --cov-report=term-missing
```

```
# command for details in case of failure
pytest -v --tb=long       # full tracebacks
pytest --pdb              # drop into debugger on failure
```