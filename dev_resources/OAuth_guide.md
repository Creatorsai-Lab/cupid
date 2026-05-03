OAuth solves a specific problem: how does Cupid get permission to read a user's YouTube data, without the user typing their Google password into Cupid?

Naive solution: ask user for their Google password. Bad — Cupid would have full access forever, and if Cupid is breached, attackers get the password.

OAuth solution: redirect the user to Google. Google asks the user (in Google's UI, with Google's security) "Do you want to give Cupid limited access?" User clicks Allow. Google hands Cupid a token — not the password — that grants only the specific permissions the user agreed to.

_The actual flow has six steps:_

```
┌─────────┐                                        ┌─────────┐
│         │  1. Click "Connect YouTube"            │         │
│  User   │ ─────────────────────────────────────▶│ Cupid    │
│ Browser │                                        │ Backend │
│         │                                        │         │
│         │  2. 302 Redirect → Google's auth URL   │         │
│         │ ◀─────────────────────────────────────│         │
└────┬────┘                                        └──────────┘
     │
     │  3. Browser follows redirect to Google
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Google                                                 │
│                                                         │
│  Shows: "Cupid wants to see your YouTube data"          │
│  User clicks ALLOW                                      │
└────┬────────────────────────────────────────────────────┘
     │
     │  4. Google redirects browser to Cupid's callback URL
     │     with ?code=ABC123 in the query string
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  User Browser hits:                                     │
│  GET /api/v1/connections/youtube/callback?code=ABC123   │
└────┬────────────────────────────────────────────────────┘
     │
     ▼
┌─────────┐                                       ┌─────────┐
│ Cupid   │  5. POST to Google's token endpoint   │ Google  │
│ Backend │  with code=ABC123 + client_secret     │  API    │
│         │ ───────────────────────────────────▶ |         │
│         │                                       │         │
│         │  6. Receives access_token +           │         │
│         │     refresh_token                     │         │
│         │ ◀────────────────────────────────────│          │
│         │                                       │         │
│         │  7. Encrypts and stores in DB         │         │
└─────────┘                                       └─────────┘
```

**Two security details that matter:**

The code is single-use, short-lived. That code=ABC123 works exactly once and expires in ~10 minutes. Even if leaked, it's worthless after one exchange or after 10 minutes.

The CSRF state token. When Cupid generates the auth URL in step 2, it includes a random state=xyz parameter. Google passes that back unchanged in step 4. Cupid verifies the returned state matches what we sent. This prevents an attacker from tricking the user into linking the attacker's YouTube account to the user's Cupid account (a real attack class called "OAuth CSRF").