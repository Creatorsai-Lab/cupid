"""The caller's real IP address, as seen through our reverse proxy.

In production the app sits behind a proxy (Coolify's Traefik), so
request.client.host is the proxy's address, not the user's. Each proxy appends
the address it received the request from to X-Forwarded-For. Anything left of
our own proxies' entries is client-supplied and can be forged, so we count
`trusted_proxy_count` entries in from the right and take that one.

    trusted_proxy_count = 1   "forged, 203.0.113.7"  ->  203.0.113.7
"""

from __future__ import annotations

from fastapi import Request

from app.config import settings


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_count
    forwarded = request.headers.get("x-forwarded-for")
    if hops <= 0 or not forwarded:
        return peer

    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not chain:
        return peer
    # Fewer entries than proxies: the leftmost is the best we have.
    return chain[-hops] if len(chain) >= hops else chain[0]
