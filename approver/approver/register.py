"""Register the approver as a Switch agent (once). Saves {id, api_key, bridge_url} to switch/state/approver/credentials.json
(gitignored, mode 600); the container mounts it read-only. Usage (phase7.py's `approver` step runs this):

    APPROVER_REGISTRATION_TOKEN=... SWITCH_BRIDGE_URL=... python -m approver.register [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

NAME = "approver"
CREDENTIALS = Path(os.environ.get("APPROVER_CREDENTIALS",
                                 Path(__file__).resolve().parents[2] / "switch" / "state" / "approver" / "credentials.json"))


def registration_body(overwrite: bool) -> dict:
    return {
        "name": NAME,
        "display_name": "Approver",
        "description": "Signs a disclosure approval when its company's owner addresses it in their private room "
                       "(`@approver approve D-…`). Deterministic, no AI; holds the signing key.",
        "connector_type": "crosswire-approver",
        "integration_profile": {"connection_model": "always_on", "message_exchange": True,
                                "pre_invocation_mediation": [], "post_invocation_mediation": [], "event_reporting": []},
        "metadata": {"project": "crosswire"},
        "overwrite": overwrite,
    }


def register(url: str, token: str, overwrite: bool) -> dict:
    with httpx.Client(base_url=url, timeout=30) as http:
        if http.get("/health").status_code != 200:
            raise SystemExit(f"GET {url}/health failed: not the agent bridge base URL")
        r = http.post("/agents", json=registration_body(overwrite), headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 409:
        raise SystemExit("an agent named 'approver' already exists; rerun with --force to overwrite it (new API key)")
    if r.status_code not in (200, 201):
        raise SystemExit(f"registration failed: HTTP {r.status_code} {r.text[:300]}")
    d = r.json()
    return {"id": d["id"], "api_key": d["api_key"], "bridge_url": url, "name": NAME,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    token, url = os.environ.get("APPROVER_REGISTRATION_TOKEN"), os.environ.get("SWITCH_BRIDGE_URL", "").rstrip("/")
    if not token or not url:
        print("APPROVER_REGISTRATION_TOKEN and SWITCH_BRIDGE_URL must be set", file=sys.stderr)
        return 2
    if CREDENTIALS.exists() and not args.force:
        print(f"{CREDENTIALS} already exists; the approver is registered (use --force to re-register)", file=sys.stderr)
        return 2
    creds = register(url, token, args.force)
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS.write_text(json.dumps(creds, indent=1))
    os.chmod(CREDENTIALS, 0o600)
    print(f"registered approver {creds['id']}; credentials saved (mode 600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
