"""python -m notary: run the Notary (needs .credentials.json from notary.register)."""

from __future__ import annotations

import asyncio
import sys

from .agent import Notary, State, log
from .client import SwitchClient, SwitchError
from .config import STATE, bridge_url, load_credentials


async def amain() -> int:
    creds = load_credentials()
    state = State(STATE)
    client = SwitchClient(bridge_url(creds), creds["id"], creds["api_key"], state.connection_id)
    try:
        await client.probe()
        ops = await client.discover_ops()
        log(f"bridge ok, {len(ops)} operations; connection id {state.connection_id}")
        await Notary(client, state).run()
    except SwitchError as exc:
        log(f"fatal: {exc}")
        return 1
    finally:
        await client.aclose()
    return 0


def main() -> None:
    try:
        sys.exit(asyncio.run(amain()))
    except KeyboardInterrupt:
        sys.exit(130)


main()
