```
┌──────────────────────────────────────────────────────────────┐
│ 1. USER LOGS IN                                                │
│    Frontend → POST /api/v1/auth/login (email + password)       │
│                                                                 │
│ 2. BACKEND VALIDATES                                            │
│    Postgres confirms credentials                               │
│                                                                 │
│ 3. BACKEND SETS COOKIE                                          │
│    Response includes: Set-Cookie: session=abc123; HttpOnly;    │
│                                                  Secure; SameSite│
│                                                                 │
│ 4. BROWSER STORES COOKIE                                        │
│    Stored automatically. JavaScript CANNOT read it (HttpOnly)  │
│                                                                 │
│ 5. EVERY FUTURE REQUEST                                         │
│    Browser auto-attaches the cookie because of                 │
│    `credentials: "include"`                                     │
│                                                                 │
│ 6. BACKEND READS COOKIE                                         │
│    `get_current_user` reads it from request.cookies            │
└──────────────────────────────────────────────────────────────┘
```

- Project uses HTTP-only cookies, not JWT tokens stored in JavaScript. This is a more secure pattern, and the magic is in this one line in api.ts:
```typescript
credentials: "include",
```
- **What credentials: "include" Means in Detail:**By default, `fetch()` does NOT send cookies on cross-origin requests. Your frontend is on `localhost:3000` and your backend is on localhost:8000 — different origins. Without `credentials: "include"`, the browser strips cookies before sending.
    - `credentials: "omit"` - never send cookies (default for cross-origin)
    - `credentials: "same-origin`" - send only if same origin
    - `credentials: "include"` - send always, even cross-origin
- The frontend never touches the token. It's invisible. This is why you don't have a `getAuthToken()` function or `localStorage.getItem("auth_token")` anywhere, the browser handles it transparently.


### HttpOnly cookie approach (better than localstorage token) (Cupid have):

- Token in cookie, marked HttpOnly
- JavaScript literally cannot access it
- Browser auto-sends with each request
- XSS-resistant — even if someone injects a script, they can't read the cookie
- Backend manages the lifecycle