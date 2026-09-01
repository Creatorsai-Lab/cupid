# CUPID Update Log

## 2026-08-30 - Security and deployment hardening

- Prevented reflected XSS in the YouTube OAuth callback by escaping dynamic
  HTML messages and returning generic user-facing errors instead of exception
  details.
- Made the API CORS allowlist use the configured `FRONTEND_URL`, enabling a
  deployed frontend while continuing to reject unknown origins.
- Rejected disabled users in `get_current_user()` so deactivating an account
  immediately blocks its existing authenticated requests.
- Made the authentication cookie environment-aware: local development permits
  HTTP, while production adds the `Secure` flag and requires HTTPS.
- Added focused regression tests for OAuth HTML escaping, CORS origin handling,
  and development/production authentication cookie behavior.
