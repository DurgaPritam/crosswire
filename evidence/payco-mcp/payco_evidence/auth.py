"""Per-company bearer token for the evidence server (gap 9). `just setup` creates the token once
(switch/state/evidence-tokens.json, gitignored), puts it in the company agent's .mcp.json headers and in this
container's env (EVIDENCE_TOKEN, via switch/state/<company>-evidence.env). Without the token: 401. If the
container has no token configured it serves as before and says so in its log (preflight fails that case)."""
from __future__ import annotations

import hmac
import os
import sys


def require_token(app):
    token = os.environ.get("EVIDENCE_TOKEN", "")
    if not token:
        print("evidence: no EVIDENCE_TOKEN configured; serving WITHOUT authentication", file=sys.stderr, flush=True)
        return app
    expected = f"Bearer {token}".encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            got = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not hmac.compare_digest(got, expected):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b'{"error": "missing or wrong evidence token"}'})
                return
        await app(scope, receive, send)

    return guarded
