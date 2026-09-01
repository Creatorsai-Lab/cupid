# Google-Only Session Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining password-login assumptions and make the backend HttpOnly cookie the only authority for whether the frontend is authenticated.

**Architecture:** The frontend uses a three-state session model (`checking`, `authenticated`, `unauthenticated`) and verifies `/api/v1/auth/me` whenever the application starts. Zustand stores only in-memory display data; it never persists an authentication decision. The backend uses one configured lifetime for both the JWT and cookie, and verified Google login progressively upgrades legacy password users without dropping their old database column during this rollout.

**Tech Stack:** Next.js 16, React 19, Zustand 5, Vitest, React Testing Library, FastAPI, Pydantic Settings, python-jose, SQLAlchemy, Alembic, PostgreSQL.

**Spec:** This plan is the canonical written form of the session design approved in chat on 2026-09-01; there is no separate spec document.

## Global Constraints

- Google OAuth is the only user-facing sign-in and signup mechanism.
- The HttpOnly backend cookie and `/api/v1/auth/me` are the authentication source of truth.
- Never persist `isAuthenticated` or an equivalent trusted flag in browser storage.
- Never edit or delete existing Alembic migration files.
- Keep the nullable `hashed_password` column during this rollout so legacy-user migration is reversible.
- Use `/signin` as the only frontend authentication route.
- Keep `SameSite=Lax`; deploy frontend and API on same-site HTTPS domains.
- Write each regression test first and observe the expected failure before changing production code.

**Current workspace note:** `frontend/lib/store.ts` has already been partially edited to remove `persist()`, but `create<AuthState>()()` has no initializer and the file will not compile. In Task 2, replace the entire file with the provided implementation block rather than trying to extend the partial version.

---

## File Map

- Create `frontend/vitest.config.ts`: Vitest configuration and `@` path alias.
- Create `frontend/test/setup.ts`: DOM cleanup and mock restoration.
- Create `frontend/lib/store.test.ts`: authentication state transition tests.
- Modify `frontend/lib/store.ts`: in-memory three-state authentication store.
- Create `frontend/lib/api.test.ts`: 401 state-clearing regression test.
- Modify `frontend/lib/api.ts`: remove legacy `/login` redirect behavior.
- Create `frontend/components/AuthSession.tsx`: one backend session check per app load.
- Create `frontend/components/AuthSession.test.tsx`: valid and missing session tests.
- Modify `frontend/app/layout.tsx`: mount `AuthSession` before auth-dependent UI.
- Modify `frontend/components/Header.tsx`: render navigation only after server verification.
- Modify `frontend/components/ProtectedRoute.tsx`: redirect only from authoritative auth state.
- Create `frontend/app/(dashboard)/layout.tsx`: protect the dashboard route group centrally.
- Modify six dashboard pages: remove duplicate `ProtectedRoute` wrappers.
- Modify `frontend/app/(auth)/complete/page.tsx`: use the new store actions.
- Modify `frontend/app/(dashboard)/settings/page.tsx`: use the new logout state action.
- Modify `backend/app/config.py`: define one session TTL.
- Modify `backend/.env.example`: document the session TTL.
- Modify `backend/app/core/security.py`: derive JWT expiry from settings and remove password helpers.
- Modify `backend/app/routers/auth.py`: derive cookie lifetime from the same setting.
- Modify `backend/tests/unit/test_auth_cookie.py`: verify cookie lifetime.
- Create `backend/tests/unit/test_session_token.py`: verify JWT lifetime.
- Modify `backend/app/services/auth.py`: progressively link legacy users to Google.
- Modify `backend/app/routers/oauth_google.py`: use the linking service and reject inactive users before issuing a cookie.
- Create `backend/tests/unit/test_google_account_linking.py`: protect legacy linking behavior.
- Modify `backend/requirements.txt`: remove unused password libraries after the usage audit.
- Modify `frontend/app/(staticpages)/cookies/page.tsx`: stop describing local storage as session authority.
- Modify `update_log.md`: record the completed authentication migration.

---

### Task 1: Add Frontend Authentication Test Infrastructure

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/test/setup.ts`

**Interfaces:**
- Consumes: existing Next.js TypeScript configuration and `@/*` alias.
- Produces: `npm test` and a jsdom environment for Tasks 2-6.

- [ ] **Step 1: Install test dependencies**

Run from `frontend`:

```powershell
npm install --save-dev vitest jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 2: Add test scripts to `package.json`**

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: Create `vitest.config.ts`**

```typescript
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

- [ ] **Step 4: Create `test/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
```

- [ ] **Step 5: Verify the empty harness**

Run: `npm test -- --passWithNoTests`

Expected: exit code 0 with no test-discovery errors.

- [ ] **Step 6: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/test/setup.ts
git commit -m "test: add frontend auth test harness"
```

---

### Task 2: Replace Persisted Authentication With In-Memory Session State

**Files:**
- Create: `frontend/lib/store.test.ts`
- Modify: `frontend/lib/store.ts`

**Interfaces:**
- Produces: `AuthStatus`, `AuthUser`, `setAuthenticated(user)`, `setUnauthenticated()`, and `setChecking()`.
- Consumes: no backend API; this task tests state transitions only.

- [ ] **Step 1: Write the failing store tests**

```typescript
import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "@/lib/store";

const user = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "creator@example.com",
  full_name: "Test Creator",
};

describe("authentication store", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, status: "checking" });
    localStorage.clear();
  });

  it("starts in checking state without trusting browser storage", () => {
    expect(useAuthStore.getState().status).toBe("checking");
    expect(localStorage.getItem("cupid-auth")).toBeNull();
  });

  it("stores a backend-verified user in memory", () => {
    useAuthStore.getState().setAuthenticated(user);

    expect(useAuthStore.getState()).toMatchObject({
      user,
      status: "authenticated",
    });
    expect(localStorage.getItem("cupid-auth")).toBeNull();
  });

  it("clears the user when the backend rejects the session", () => {
    useAuthStore.getState().setAuthenticated(user);
    useAuthStore.getState().setUnauthenticated();

    expect(useAuthStore.getState()).toMatchObject({
      user: null,
      status: "unauthenticated",
    });
  });
});
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `npm test -- lib/store.test.ts`

Expected on the current workspace: FAIL because the partial store has no Zustand initializer. On the pre-edit commit, the same tests fail because `status`, `setAuthenticated`, and `setUnauthenticated` do not exist and the old store writes `cupid-auth`.

- [ ] **Step 3: Replace `store.ts` with the minimal in-memory store**

```typescript
import { create } from "zustand";

export type AuthStatus = "checking" | "authenticated" | "unauthenticated";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
}

interface AuthState {
  user: AuthUser | null;
  status: AuthStatus;
  setChecking: () => void;
  setAuthenticated: (user: AuthUser) => void;
  setUnauthenticated: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "checking",
  setChecking: () => set({ status: "checking" }),
  setAuthenticated: (user) => set({ user, status: "authenticated" }),
  setUnauthenticated: () => set({ user: null, status: "unauthenticated" }),
}));
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `npm test -- lib/store.test.ts`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/store.ts frontend/lib/store.test.ts
git commit -m "fix: make backend session authoritative"
```

---

### Task 3: Remove the Legacy `/login` Redirect From API Handling

**Files:**
- Create: `frontend/lib/api.test.ts`
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Consumes: `useAuthStore.getState().setUnauthenticated()` from Task 2.
- Produces: API requests that clear auth state on `401` and throw `ApiError` without navigating.

- [ ] **Step 1: Write the failing 401 regression test**

```typescript
import { beforeEach, expect, it, vi } from "vitest";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

beforeEach(() => {
  useAuthStore.setState({
    user: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "creator@example.com",
      full_name: "Test Creator",
    },
    status: "authenticated",
  });
});

it("clears auth state on 401 without redirecting to a removed route", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(authApi.me()).rejects.toMatchObject({ status: 401 });
  expect(useAuthStore.getState().status).toBe("unauthenticated");
  expect(window.location.pathname).not.toBe("/login");
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm test -- lib/api.test.ts`

Expected: FAIL because the current handler calls the removed `clearUser()` and redirects to `/login`.

- [ ] **Step 3: Replace `handle401()`**

```typescript
async function handle401() {
  const { useAuthStore } = await import("@/lib/store");
  useAuthStore.getState().setUnauthenticated();
}
```

Keep both request helpers calling `handle401()` before throwing `ApiError`. Remove the obsolete `/api/v1/auth/login` exception and every reference to `/login`.

- [ ] **Step 4: Run the test and verify GREEN**

Run: `npm test -- lib/api.test.ts`

Expected: 1 passed with no jsdom navigation warning.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "fix: remove legacy login redirect"
```

---

### Task 4: Bootstrap the Frontend From the Backend Session

**Files:**
- Create: `frontend/components/AuthSession.tsx`
- Create: `frontend/components/AuthSession.test.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/components/Header.tsx`

**Interfaces:**
- Consumes: `authApi.me()`, `setAuthenticated()`, and `setUnauthenticated()`.
- Produces: one session check on application mount and no authenticated-header flash.

- [ ] **Step 1: Write failing bootstrap tests**

Mock only the external HTTP boundary, `authApi.me()`. Render the real `AuthSession` and assert the real Zustand state:

```typescript
import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import AuthSession from "@/components/AuthSession";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

vi.mock("@/lib/api", () => ({
  authApi: { me: vi.fn() },
}));

beforeEach(() => {
  useAuthStore.setState({ user: null, status: "checking" });
});

it("hydrates a valid backend session", async () => {
  vi.mocked(authApi.me).mockResolvedValue({
    success: true,
    data: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "creator@example.com",
      full_name: "Test Creator",
      is_active: true,
      created_at: "2026-09-01T00:00:00Z",
    },
    error: null,
  });

  render(<AuthSession />);

  await waitFor(() =>
    expect(useAuthStore.getState().status).toBe("authenticated"),
  );
});

it("marks a missing or expired session unauthenticated", async () => {
  vi.mocked(authApi.me).mockRejectedValue(new Error("401"));

  render(<AuthSession />);

  await waitFor(() =>
    expect(useAuthStore.getState().status).toBe("unauthenticated"),
  );
});
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `npm test -- components/AuthSession.test.tsx`

Expected: FAIL because `AuthSession` does not exist.

- [ ] **Step 3: Create `AuthSession.tsx`**

```typescript
"use client";

import { useEffect } from "react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

export default function AuthSession() {
  const setAuthenticated = useAuthStore((state) => state.setAuthenticated);
  const setUnauthenticated = useAuthStore((state) => state.setUnauthenticated);

  useEffect(() => {
    localStorage.removeItem("cupid-auth");

    authApi
      .me()
      .then((response) =>
        setAuthenticated({
          id: response.data.id,
          email: response.data.email,
          full_name: response.data.full_name,
        }),
      )
      .catch(setUnauthenticated);
  }, [setAuthenticated, setUnauthenticated]);

  return null;
}
```

- [ ] **Step 4: Mount it in `app/layout.tsx` before `Header`**

```tsx
<body>
  <AuthSession />
  <Header />
  {children}
  <Assistant />
</body>
```

- [ ] **Step 5: Make `Header` use `status`**

Replace `isAuthenticated` reads with:

```typescript
const status = useAuthStore((state) => state.status);
const isAuthenticated = status === "authenticated";
```

While `status === "checking"`, show neither authenticated navigation nor the “Get started” command. Keep the logo visible.

- [ ] **Step 6: Run tests and frontend validation**

```powershell
npm test -- components/AuthSession.test.tsx
npm run typecheck
```

Expected: bootstrap tests pass and TypeScript reports no errors.

- [ ] **Step 7: Commit**

```powershell
git add frontend/components/AuthSession.tsx frontend/components/AuthSession.test.tsx frontend/components/Header.tsx frontend/app/layout.tsx
git commit -m "feat: restore auth state from backend cookie"
```

---

### Task 5: Protect the Entire Dashboard Route Group Centrally

**Files:**
- Modify: `frontend/components/ProtectedRoute.tsx`
- Create: `frontend/components/ProtectedRoute.test.tsx`
- Create: `frontend/app/(dashboard)/layout.tsx`
- Modify: `frontend/app/(dashboard)/create/page.tsx`
- Modify: `frontend/app/(dashboard)/trends/page.tsx`
- Modify: `frontend/app/(dashboard)/insights/page.tsx`
- Modify: `frontend/app/(dashboard)/history/page.tsx`
- Modify: `frontend/app/(dashboard)/earn/page.tsx`
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Interfaces:**
- Consumes: authoritative `status` from Task 2.
- Produces: one guard for all current and future dashboard pages.

- [ ] **Step 1: Write failing guard tests**

Mock `useRouter()` and assert behavior of the real guard:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

beforeEach(() => {
  replace.mockReset();
  useAuthStore.setState({ user: null, status: "checking" });
});

it("waits while the backend session is being checked", () => {
  render(<ProtectedRoute>private</ProtectedRoute>);
  expect(screen.queryByText("private")).not.toBeInTheDocument();
  expect(replace).not.toHaveBeenCalled();
});

it("redirects an unauthenticated visitor to signin", async () => {
  useAuthStore.setState({ user: null, status: "unauthenticated" });
  render(<ProtectedRoute>private</ProtectedRoute>);
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/signin"));
});

it("renders children only for an authenticated session", () => {
  useAuthStore.setState({ status: "authenticated" });
  render(<ProtectedRoute>private</ProtectedRoute>);
  expect(screen.getByText("private")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `npm test -- components/ProtectedRoute.test.tsx`

Expected: FAIL because the component still reads `_hasHydrated` and `isAuthenticated`.

- [ ] **Step 3: Update `ProtectedRoute`**

```typescript
const status = useAuthStore((state) => state.status);

useEffect(() => {
  if (status === "unauthenticated") {
    router.replace("/signin");
  }
}, [router, status]);

if (status !== "authenticated") return null;
return <>{children}</>;
```

- [ ] **Step 4: Add the dashboard layout**

```tsx
import ProtectedRoute from "@/components/ProtectedRoute";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
```

- [ ] **Step 5: Remove page-level guards**

In each of the six dashboard pages, remove the `ProtectedRoute` import and the outer `<ProtectedRoute>...</ProtectedRoute>` wrapper. Do not alter the page’s inner UI or data-fetching logic.

- [ ] **Step 6: Verify**

```powershell
npm test -- components/ProtectedRoute.test.tsx
npm run typecheck
npm run build
```

Expected: 3 guard tests pass and the production build succeeds.

- [ ] **Step 7: Commit**

```powershell
git add frontend/components/ProtectedRoute.tsx frontend/components/ProtectedRoute.test.tsx 'frontend/app/(dashboard)'
git commit -m "refactor: guard dashboard routes centrally"
```

---

### Task 6: Update OAuth Completion and Logout to the New Store Contract

**Files:**
- Modify: `frontend/app/(auth)/complete/page.tsx`
- Modify: `frontend/app/(dashboard)/settings/page.tsx`
- Modify: `frontend/app/(auth)/signin/page.tsx`

**Interfaces:**
- Consumes: `setAuthenticated()` and `setUnauthenticated()` from Task 2.
- Produces: OAuth completion and logout with no legacy route references.

- [ ] **Step 1: Update `/complete`**

Replace `setUser` with `setAuthenticated`. Keep the current internal-only `next` validation and `/signin?error=session` fallback.

- [ ] **Step 2: Update logout**

Replace `clearUser()` with `setUnauthenticated()` and use:

```typescript
router.replace("/signin");
```

- [ ] **Step 3: Add a disabled-account message**

Extend the sign-in error map:

```typescript
disabled: "This account has been disabled. Contact support if this is unexpected.",
```

- [ ] **Step 4: Verify no active legacy routes remain**

Run:

```powershell
rg -n '"/login"|/api/v1/auth/login|/api/v1/auth/register|clearUser|setUser' frontend --glob '!tsconfig.tsbuildinfo'
```

Expected: no active authentication-code matches. Comments using the generic words “login” or “signup” do not count.

- [ ] **Step 5: Verify frontend**

```powershell
npm test
npm run typecheck
npm run build
```

- [ ] **Step 6: Commit**

```powershell
git add 'frontend/app/(auth)' 'frontend/app/(dashboard)/settings/page.tsx'
git commit -m "fix: complete google-only frontend auth flow"
```

---

### Task 7: Align JWT and Cookie Lifetimes

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/unit/test_auth_cookie.py`
- Create: `backend/tests/unit/test_session_token.py`

**Interfaces:**
- Produces: `settings.session_ttl_seconds: int` used by both token and cookie creation.
- Consumes: stable `settings.secret_key` shared by all backend workers.

- [ ] **Step 1: Extend the cookie regression test**

In `test_auth_cookie.py`, set a test TTL and assert the emitted Max-Age:

```python
monkeypatch.setattr(settings, "session_ttl_seconds", 600)
cookie = _auth_cookie_for("development", monkeypatch)[COOKIE_KEY]
assert cookie["max-age"] == "600"
```

- [ ] **Step 2: Write the failing JWT lifetime test**

```python
from datetime import UTC, datetime

from jose import jwt

from app.config import settings
from app.core.security import ALGORITHM, create_access_token


def test_access_token_uses_configured_session_lifetime(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_ttl_seconds", 600)

    before = int(datetime.now(UTC).timestamp())
    token = create_access_token("user-123")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    after = int(datetime.now(UTC).timestamp())

    assert before + 600 <= payload["exp"] <= after + 600
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/test_auth_cookie.py tests/unit/test_session_token.py -q
```

Expected: FAIL because the cookie is fixed at seven days and JWT is fixed at 30 minutes.

- [ ] **Step 4: Add the setting**

```python
session_ttl_seconds: int = 60 * 60 * 24 * 7
```

Add to `.env.example`:

```env
SESSION_TTL_SECONDS=604800
```

- [ ] **Step 5: Use the setting for JWT and cookie**

In `core/security.py`:

```python
expire = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
```

In `routers/auth.py`:

```python
max_age=settings.session_ttl_seconds,
```

Remove `ACCESS_TOKEN_EXPIRE_MINUTES` and `COOKIE_MAX_AGE` so a second source of truth cannot return.

- [ ] **Step 6: Run tests and verify GREEN**

```powershell
python -m pytest tests/unit/test_auth_cookie.py tests/unit/test_session_token.py -q
ruff check app/config.py app/core/security.py app/routers/auth.py tests/unit/test_auth_cookie.py tests/unit/test_session_token.py
```

- [ ] **Step 7: Commit**

```powershell
git add backend/app/config.py backend/.env.example backend/app/core/security.py backend/app/routers/auth.py backend/tests/unit/test_auth_cookie.py backend/tests/unit/test_session_token.py
git commit -m "fix: align cookie and token session lifetime"
```

---

### Task 8: Progressively Migrate Legacy Password Users to Google

**Files:**
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/routers/oauth_google.py`
- Create: `backend/tests/unit/test_google_account_linking.py`

**Interfaces:**
- Produces: `link_google_identity(user: User, info: dict[str, object]) -> None`.
- Consumes: a Google profile whose `email_verified` and `email` checks already passed.

- [ ] **Step 1: Write failing linking tests**

```python
from app.models.user import User
from app.services.auth import link_google_identity


def test_link_google_identity_upgrades_a_legacy_user() -> None:
    user = User(
        full_name="Legacy Creator",
        email="creator@example.com",
        hashed_password="legacy-hash",
        auth_provider="password",
    )

    link_google_identity(
        user,
        {
            "sub": "google-account-123",
            "name": "Google Creator",
            "picture": "https://example.com/avatar.png",
        },
    )

    assert user.auth_provider == "google"
    assert user.provider_account_id == "google-account-123"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert user.hashed_password is None


def test_link_google_identity_keeps_existing_name_when_google_name_is_missing() -> None:
    user = User(
        full_name="Existing Name",
        email="creator@example.com",
        hashed_password=None,
        auth_provider="google",
    )

    link_google_identity(user, {"sub": "google-account-123"})

    assert user.full_name == "Existing Name"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/unit/test_google_account_linking.py -q`

Expected: FAIL because `link_google_identity` does not exist.

- [ ] **Step 3: Implement the pure linking function**

```python
from typing import Any


def link_google_identity(user: User, info: dict[str, Any]) -> None:
    user.auth_provider = "google"
    user.provider_account_id = str(info["sub"])
    user.avatar_url = str(info["picture"]) if info.get("picture") else None
    if info.get("name"):
        user.full_name = str(info["name"])
    user.hashed_password = None
```

- [ ] **Step 4: Update the OAuth callback**

After looking up an existing user and before issuing a cookie:

```python
if user is not None and not user.is_active:
    return _bounce("/signin?error=disabled")

if user is not None:
    link_google_identity(user, info)
    await db.commit()
    await db.refresh(user)
```

For a newly created user, keep the existing creation flow. Do not create a second account when the verified Google email matches an existing legacy account.

- [ ] **Step 5: Run tests and lint**

```powershell
python -m pytest tests/unit/test_google_account_linking.py -q
ruff check app/services/auth.py app/routers/oauth_google.py tests/unit/test_google_account_linking.py
```

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/auth.py backend/app/routers/oauth_google.py backend/tests/unit/test_google_account_linking.py
git commit -m "feat: migrate legacy users on google sign-in"
```

---

### Task 9: Remove Unused Password Code Without Dropping Legacy Data

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/requirements.txt`
- Modify: `frontend/app/(staticpages)/cookies/page.tsx`
- Modify: `update_log.md`

**Interfaces:**
- Consumes: successful Google account linking from Task 8.
- Produces: no executable password-authentication code while retaining the nullable database column for rollback safety.

- [ ] **Step 1: Confirm password helpers have no consumers**

Run:

```powershell
rg -n "hash_password|verify_password|import bcrypt|import passlib" backend --glob '!backend/.venv/**'
```

Expected: matches only `backend/app/core/security.py` and dependency declarations.

- [ ] **Step 2: Remove password code**

Delete `hash_password()`, `verify_password()`, the `bcrypt` import, and password-hashing documentation from `core/security.py`. Keep JWT creation and decoding unchanged except for Task 7’s lifetime configuration.

- [ ] **Step 3: Remove unused dependencies**

Delete the `bcrypt` and `passlib` lines from `backend/requirements.txt`. Do not uninstall them manually from the active virtual environment; a future clean installation verifies the requirement file.

- [ ] **Step 4: Correct the cookie-page description**

State that the HttpOnly cookie maintains the session and local storage is used only for non-sensitive interface preferences. Do not claim local storage authenticates the user.

- [ ] **Step 5: Keep database history intact**

Do not modify:

```text
backend/alembic/versions/5570cf9e60b2_create_users_table.py
backend/alembic/versions/fa402c40d6d7_google_login_nullable_password_provider_.py
```

Do not drop `User.hashed_password` in this rollout. After production has run long enough to migrate active legacy users, check:

```sql
SELECT auth_provider, COUNT(*) FROM users GROUP BY auth_provider;
SELECT COUNT(*) FROM users WHERE hashed_password IS NOT NULL;
```

A later migration may drop the column only when the second query returns zero and product owners confirm no password rollback is required.

- [ ] **Step 6: Update `update_log.md`**

Record:

- backend-authoritative frontend sessions;
- removal of the stale `/login` redirect;
- aligned JWT/cookie lifetime;
- progressive Google linking for legacy users;
- removal of unused password code while retaining the transitional column.

- [ ] **Step 7: Run complete verification**

Backend:

```powershell
cd D:\Cupid\backend
$env:DEBUG='true'
python -m pytest tests/unit/test_auth_cookie.py tests/unit/test_session_token.py tests/unit/test_google_account_linking.py tests/unit/test_frontend_security.py tests/unit/test_connections_html.py -q
ruff check app tests
ruff format --check app tests
```

Frontend:

```powershell
cd D:\Cupid\frontend
npm test
npm run typecheck
npm run lint
npm run build
```

- [ ] **Step 8: Perform browser acceptance checks**

1. Clear `cupid-auth` and the `cupid_access_token` cookie.
2. Open `/`; verify no authenticated navigation appears.
3. Open `/create`; verify redirect to `/signin`, never `/login`.
4. Complete Google sign-in; verify `/complete` calls `/api/v1/auth/me` and reaches `/create` or `/settings`.
5. Refresh; verify `/api/v1/auth/me` returns `200` and the authenticated header appears only afterward.
6. Delete the cookie and refresh; verify the app becomes unauthenticated.
7. Log out; verify the cookie disappears and `/create` redirects to `/signin`.
8. Disable the user in admin; verify the next `/me` returns `401` and the app shows `/signin`.
9. Test production cookie behavior only over HTTPS; `APP_ENV=production` on plain localhost intentionally prevents the Secure cookie from being stored.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/core/security.py backend/requirements.txt 'frontend/app/(staticpages)/cookies/page.tsx' update_log.md
git commit -m "chore: remove legacy password auth remnants"
```

---

## Production Deployment Checklist

- [ ] `SECRET_KEY` is a strong fixed secret and is identical across all API workers.
- [ ] `APP_ENV=production` is set only on HTTPS deployment environments.
- [ ] `SESSION_TTL_SECONDS=604800` is configured or intentionally changed.
- [ ] `FRONTEND_URL=https://app.example.com` contains only the frontend origin.
- [ ] `NEXT_PUBLIC_API_URL=https://api.example.com` points to the deployed API.
- [ ] Frontend and API share the same registrable domain so `SameSite=Lax` works reliably.
- [ ] Google OAuth authorized redirect URI exactly matches `GOOGLE_LOGIN_REDIRECT_URI`.
- [ ] Only one canonical frontend `/signin` route exists.
- [ ] A deployment restart does not regenerate `SECRET_KEY`.
- [ ] Browser acceptance checks pass on the staging HTTPS domains before production rollout.
