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


class Budget:
    """Gap 6 leakage budget: at most FINGERPRINT_BUDGET distinct events fingerprinted per salt (default 5). Asking
    again for an event already fingerprinted under that salt is free; a new salt starts a new budget."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit if limit is not None else int(os.environ.get("FINGERPRINT_BUDGET", "5"))
        self.used: dict[str, set[str]] = {}

    def spend(self, salt: str, event_id: str) -> None:
        events = self.used.setdefault(salt, set())
        if event_id not in events and len(events) >= self.limit:
            raise PermissionError(f"leakage budget reached: {self.limit} events already fingerprinted with this salt "
                                  "(ask the mediator which events the incident needs)")
        events.add(event_id)
