"""One-time registration of the Notary as an always_on Switch agent.

    NOTARY_REGISTRATION_TOKEN=<token> SWITCH_BRIDGE_URL=http://127.0.0.1:<port> python -m notary.register

The registration token is a Gateway user's registration key (create it while signed in as
`host`, who becomes the Notary's owner). It is read from the environment, never printed,
and never stored. The API key comes back ONCE and is saved to .credentials.json (mode 600).

Uses the lower-level `POST /agents` with an integration profile, because `register-known`
only accepts known provider kinds (claude-code, codex, ...), and `always_on` is a
connection model, not a provider kind.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

import httpx

from .config import CREDENTIALS, bridge_url

NAME = "notary"


def registration_body(overwrite: bool) -> dict:
    return {
        "name": NAME,
        "display_name": "Notary",
        "description": "Deterministic byte-fingerprint comparator for Crosswire incidents (no AI). "
                       "Address it with `compare <D-PAY-n> <D-SHOP-n>` or `help`.",
        "connector_type": "crosswire-notary",
        "integration_profile": {
            "connection_model": "always_on",
            "message_exchange": True,
            "pre_invocation_mediation": [],
            "post_invocation_mediation": [],
            "event_reporting": [],
        },
        "metadata": {"project": "crosswire"},
        "overwrite": overwrite,
    }


async def register(url: str, token: str, overwrite: bool, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    async with httpx.AsyncClient(base_url=url, transport=transport, timeout=30) as http:
        health = await http.get("/health")
        if health.status_code != 200:
            raise SystemExit(f"GET {url}/health returned {health.status_code}: not the agent bridge base URL")
        r = await http.post("/agents", json=registration_body(overwrite), headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 409:
        raise SystemExit("an agent named 'notary' already exists; rerun with --force to overwrite it (new API key)")
    if r.status_code != 200 and r.status_code != 201:
        raise SystemExit(f"registration failed: HTTP {r.status_code} {r.text[:300]}")
    data = r.json()
    return {"id": data["id"], "api_key": data["api_key"], "bridge_url": url, "name": NAME,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="overwrite an existing notary agent and credentials")
    args = ap.parse_args(argv)
    token = os.environ.get("NOTARY_REGISTRATION_TOKEN")
    if not token:
        print("NOTARY_REGISTRATION_TOKEN is not set", file=sys.stderr)
        return 2
    if CREDENTIALS.exists() and not args.force:
        print(f"{CREDENTIALS} already exists; the notary is registered. Use --force to re-register.", file=sys.stderr)
        return 2
    creds = asyncio.run(register(bridge_url(), token, args.force))
    CREDENTIALS.write_text(json.dumps(creds, indent=1))
    os.chmod(CREDENTIALS, 0o600)
    print(f"registered notary {creds['id']}; credentials saved to {CREDENTIALS} (mode 600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
