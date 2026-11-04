#!/usr/bin/env python3
"""Send 60 payment.succeeded webhooks through PayCo's admin API: 54 ASCII customer names
and 6 non-ASCII ones at fixed positions (deterministic, so event ids line up after
`just reset`: evt_0042 is Chloé Martin, one accented character, +4 bytes).

    scripts/simulate.py [--url http://localhost:7001] [--out .tmp/last-simulate.json]

Writes a summary for verify_bug.py: event ids, customer ids, a non_ascii flag and the
response status PayCo recorded. It never writes customer names.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NON_ASCII = {
    7: ("José Álvarez", "ES"),
    18: ("Zoë Brooks", "GB"),
    29: ("Søren Kierk", "DK"),
    42: ("Chloé Martin", "FR"),
    51: ("Łukasz Nowak", "PL"),
    58: ("Renée Dubois", "BE"),
}
FIRST = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry", "Irene", "Jack",
         "Karen", "Liam", "Maria", "Nathan", "Olivia", "Peter", "Quinn", "Rachel"]
LAST = ["Smith", "Jones", "Taylor", "Brown", "Wilson", "Clark", "Lewis", "Walker", "Young"]
COUNTRIES = ["US", "GB", "DE", "FR", "NL", "IE", "CA", "AU"]
CURRENCY = {"US": "USD", "CA": "CAD", "AU": "AUD", "GB": "GBP"}


def customers(count: int = 60) -> list[dict]:
    out = []
    ascii_i = 0
    for n in range(1, count + 1):
        if n in NON_ASCII:
            name, country = NON_ASCII[n]
        else:
            name = f"{FIRST[ascii_i % len(FIRST)]} {LAST[(ascii_i * 7) % len(LAST)]}"
            country = COUNTRIES[ascii_i % len(COUNTRIES)]
            ascii_i += 1
        out.append({"id": f"cus_{n:04d}", "name": name, "country": country,
                    "amount_cents": 500 + (n * 137) % 9500, "currency": CURRENCY.get(country, "EUR")})
    return out


def send(url: str, c: dict) -> dict:
    body = json.dumps({"customer": {"id": c["id"], "name": c["name"], "country": c["country"]},
                       "amount_cents": c["amount_cents"], "currency": c["currency"]}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/admin/send-event", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=f"http://localhost:{os.environ.get('PAYCO_API_PORT', '7001')}")
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "last-simulate.json"))
    args = ap.parse_args()

    results = []
    try:
        for c in customers():
            r = send(args.url, c)
            results.append({"event_id": r["event_id"], "customer_id": c["id"],
                            "non_ascii": not c["name"].isascii(), "response_status": r["response_status"]})
    except urllib.error.URLError as exc:
        print(f"error: cannot reach PayCo at {args.url} ({exc}). Run `just up` first.", file=sys.stderr)
        return 2
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"url": args.url, "events": results}, indent=1))

    by_status: dict[str, int] = {}
    for r in results:
        by_status[str(r["response_status"])] = by_status.get(str(r["response_status"]), 0) + 1
    print(f"sent {len(results)} events ({results[0]['event_id']}..{results[-1]['event_id']}); "
          f"ShopCo responses: {', '.join(f'{k}×{v}' for k, v in sorted(by_status.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
