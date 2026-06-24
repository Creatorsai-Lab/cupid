# Admin & Audit System — How It Works

_Last updated: 2026-06-23. Author: implemented with Claude. Scope: MVP (two
roles only — `user` and `admin`)._

This doc explains the admin security model added on top of the subscriptions
system: how an admin is designated, the two gated admin surfaces, the audit
trail, and how to operate/extend it.

---

## 1. The mental model

There are **two separate admin surfaces**, each with its own lock:

| Surface | What it's for | Lock | URL |
|---|---|---|---|
| **Admin API** (`POST /api/v1/admin/users/{id}/tier`) | Programmatic tier changes (scripts, future Stripe webhooks) | `require_admin` → reads `users.is_admin`, returns **404** to everyone else | hidden from `/api/docs` |
| **SQLAdmin dashboard** | Point-and-click viewing/editing of users, subscriptions, audit log | `AdminAuth` → separate username/password from env | `settings.admin_panel_path` (default `/ctrl-panel`) |

Both are designed so a non-admin (or a scanner) cannot tell they exist, and
every tier change is recorded in an append-only `audit_log`.

**Key security principle:** *hiding the URL is NOT security.* The real lock is
the credential/flag check. Obscure paths and "hidden from docs" are thin extra
layers, never the thing you rely on.

---

## 2. How you become an admin (the durable + easy design)

Two pieces working together:

1. **`users.is_admin`** (Boolean column) — the **durable source of truth**.
   Every admin gate reads this. It lives on the user record, so it survives the
   planned switch to social login (Google/GitHub) — the flag doesn't care how
   you authenticate.

2. **`ADMIN_EMAILS`** (env var) — the **easy designation mechanism**. At
   startup, `bootstrap_admins()` (in `app/admin/security.py`) promotes any user
   whose email is in this list to `is_admin=True`. So you never hand-edit the
   DB; you just put your email in `.env`:

   ```
   ADMIN_EMAILS=youremail@gmail.com
   ```

   It's idempotent (safe to restart), case-insensitive, and keys on the
   **verified** email you'll get from Google/GitHub later.

> Flow: put email in `ADMIN_EMAILS` → restart server → `bootstrap_admins` flips
> `is_admin=True` → every gate now lets you through.

---

## 3. The 404 gate (`require_admin`)

`app/admin/security.py`:

```python
async def require_admin(current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(404, "Not found")   # 404, not 403
    return current_user
```

Why **404 not 403**: a 403 ("Forbidden") *confirms the endpoint exists*. A 404
("Not found") makes the admin route indistinguishable from a non-existent one —
a scanner learns nothing. Combined with `include_in_schema=False` (the route is
absent from `/api/docs`), the endpoint is effectively invisible to non-admins.

Any future admin API just adds `Depends(require_admin)` and gets the same
protection for free.

---

## 4. The SQLAdmin dashboard

`app/admin/setup.py` mounts [SQLAdmin](https://github.com/aminalaee/sqladmin) —
a prebuilt admin UI over the existing SQLAlchemy models. No frontend code: each
`ModelView` renders list/detail/edit pages.

- **Mounted only if credentials are set.** No `ADMIN_PANEL_USER` /
  `ADMIN_PANEL_PASSWORD` → the panel is **not mounted at all** (never an open
  panel). This is a fail-safe default.
- **Credential wall** (`AdminAuth`): a username/password checked with
  constant-time comparison against env values. Independent of app login — a
  different surface gets a different lock.
- **Views:** `Users` (read-mostly, no delete), `Subscriptions` (editable for
  quick tier flips while testing), `Audit Log` (fully read-only — append-only).

### To enable it, add to `.env`:
```
ADMIN_PANEL_PATH=/ctrl-panel          # change to something non-obvious
ADMIN_PANEL_USER=adya
ADMIN_PANEL_PASSWORD=<long-random-password>
ADMIN_SESSION_SECRET=<long-random-string>   # signs the dashboard cookie
```
Generate secrets with: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

Then visit `http://localhost:8000/ctrl-panel` and log in.

> ⚠️ **Caveat:** editing a subscription's tier *directly in SQLAdmin* writes the
> row straight to the DB — it **bypasses** `service.set_user_tier`, so it is
> **not validated and not audited**. For an audited, validated change use the
> Admin API endpoint. Use the dashboard edit only for quick local testing.

---

## 5. The audit trail (`audit_log`)

`app/models/audit_log.py` — an **append-only** table: rows are only ever
INSERTed, never updated/deleted (enforced by convention + read-only in the UI).

Every call to `service.set_user_tier(...)` writes one row **in the same
transaction** as the tier change, so they commit together or not at all:

```
actor_id / actor_email   — WHO did it (null for system/Stripe/signup)
action                   — "tier.set"
target_type / target_id  — "user" / <user_id>
detail (JSONB)           — {from_tier, to_tier, status, reason}
created_at               — when
```

This answers "who changed this user's plan, when, and from what to what?" —
the question you can't answer retroactively unless you logged it at the time.
It's generic (action + target + JSON detail) so future admin actions can reuse
it without a schema change.

---

## 6. How to operate it

**Change a user's tier (audited):**
```bash
# you must be logged in as an admin user (cookie); POST to the hidden endpoint
curl -X POST http://localhost:8000/api/v1/admin/users/<USER_ID>/tier \
  -H "Content-Type: application/json" \
  -b "cupid_access_token=<your-cookie>" \
  -d '{"tier":"premium","reason":"testing premium UI"}'
```

**Test tiers on yourself:** set your own `user_id`, flip between
`free`/`pro`/`premium`, then re-fetch `GET /api/v1/entitlement` to see the
resolved limits change.

**Read the audit log:** open the dashboard → Audit Log (newest first), or query
`SELECT * FROM audit_log ORDER BY created_at DESC;`.

---

## 7. Future handling — extending safely

- **New admin API** → add `Depends(require_admin)` + `include_in_schema=False`.
  Done. Same 404 protection.
- **New audited action** → write an `AuditLog` row inside the service function
  that performs it (action verb like `"connection.revoke"`). Keep it in the
  same transaction as the change.
- **More roles later (support, billing…)** → replace the `is_admin` boolean with
  a `role` column and make `require_admin` / new `require_role("support")`
  read it. The call sites barely change.
- **Stripe webhooks (v2)** → they call `service.set_user_tier(...)` with
  `actor_email="stripe-webhook"` (or null) — same audited path, no new code.
- **Production checklist:**
  - Real, long random `ADMIN_PANEL_PASSWORD` + `ADMIN_SESSION_SECRET`.
  - Non-obvious `ADMIN_PANEL_PATH`.
  - Consider putting the dashboard behind VPN / IP allowlist at the proxy.
  - Never add an admin link/button to the customer-facing frontend.
  - `.env` stays gitignored; secrets injected via the host's secret manager.

---

## 8. Files involved

| File | Role |
|---|---|
| `app/models/user.py` | `is_admin` column |
| `app/models/audit_log.py` | `AuditLog` model (append-only) |
| `app/admin/security.py` | `require_admin` (404 gate), `bootstrap_admins`, `AdminAuth` |
| `app/admin/setup.py` | mounts SQLAdmin + ModelViews |
| `app/subscriptions/service.py` | `set_user_tier` writes the audit row |
| `app/subscriptions/router.py` | admin endpoint (gated, hidden, audited) |
| `app/config.py` | `admin_emails`, `admin_panel_*` settings |
| `app/main.py` | mounts dashboard, runs `bootstrap_admins` at startup |
| alembic `…_add_is_admin_column_and_audit_log_table.py` | migration |

**Migration note:** every new model **must** be imported in `alembic/env.py`, or
autogenerate will think its table was deleted and emit a destructive
`drop_table` (this exact bug dropped `user_personalization` + `trending_articles`
once — see git history). Always **read** an autogenerated migration before
applying it.
