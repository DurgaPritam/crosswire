#!/usr/bin/env python3
"""Set the design avatars (docs/design/avatars/avatar-*-512.png) as Mattermost profile images.

    .venv/bin/python scripts/avatars.py            # agents' bot accounts + priya and sam

Switch stores an agent icon only as a public https URL (it refuses local or private hosts, CHOO-2171), and the
bridge re-uploads that URL as the bot avatar. Until the repo is public there is no such URL, so this sets the
Mattermost images directly with the admin login from .env. After publishing, `--switch <raw-base-url>` also sets
each agent's Switch icon_url (PUT /gateway/agents/{id}/icon) so the Console GUI and the bridge agree.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mmlib  # noqa: E402

PNG = ROOT / "docs/design/avatars"
WHO = ["payco-agent", "shopco-agent", "mediator", "notary", "priya", "sam"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--switch", metavar="RAW_BASE_URL", help="public https base where avatar-<who>-512.png is served")
    args = ap.parse_args()
    e = mmlib.load_env()
    admin = mmlib.admin_client(e)
    own = {"priya": e.get("MM_PRIYA_PASSWORD"), "sam": e.get("MM_SAM_PASSWORD")}
    for who in WHO:
        # people set their own picture; bot accounts need a Mattermost system admin (or Switch's icon_url after publishing)
        mm = mmlib.Mattermost(e["MM_URL"]).login(who, own[who]) if own.get(who) else admin
        user = mm.user_by_name(who)
        if not user:
            print(f"{who}: no Mattermost account, skipped")
            continue
        img = PNG / f"avatar-{who}-512.png"
        r = httpx.post(f"{mm.base}/users/{user['id']}/image", headers={"Authorization": f"Bearer {mm.token}", "X-Requested-With": "XMLHttpRequest"},
                       files={"image": (img.name, img.read_bytes(), "image/png")}, timeout=30)
        print(f"{who}: Mattermost image " + ("set" if r.status_code == 200 else
              f"HTTP {r.status_code} (needs a Mattermost system admin, or --switch after publishing)"))
    if args.switch:
        import phase7
        gw = phase7.admin(phase7.env())
        ids = {a["name"]: a["id"] for a in phase7.items(gw.req("GET", "/agents"), "agents")}
        for who in WHO[:4]:
            gw.req("PUT", f"/agents/{ids[who]}/icon", {"icon_url": f"{args.switch.rstrip('/')}/avatar-{who}-512.png"})
            print(f"{who}: Switch icon_url set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
