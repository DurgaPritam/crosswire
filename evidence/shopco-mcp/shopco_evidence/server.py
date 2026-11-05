"""shopco-evidence MCP server (streamable HTTP). Mounts only ShopCo's private volume, read-only."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from . import tools

DB = os.environ.get("SHOPCO_DB", "/data/shopco/jobs.db")
PORT = int(os.environ.get("PORT", "7102"))

server = MCPServer(
    "shopco-evidence",
    instructions="ShopCo's evidence about webhook verification. Every answer is event ids, byte "
                 "offsets/lengths and salted hashes: never payload values or customer data.",
)


@server.tool()
def list_signature_failures(since_minutes: int = 1440) -> list[dict[str, Any]]:
    """Webhook events whose signature check failed in the window (event ids and times only)."""
    with tools.connect_ro(DB) as db:
        return tools.list_signature_failures(db, since_minutes)


@server.tool()
def get_verification_fingerprint(event_id: str, salt: str) -> dict[str, Any]:
    """wirecheck fingerprint of the exact bytes ShopCo verified the signature over, salted with the incident salt."""
    with tools.connect_ro(DB) as db:
        return tools.get_verification_fingerprint(db, event_id, salt)


@server.tool()
def get_verification_spec() -> dict[str, Any]:
    """What ShopCo's signature verifier does, in prose (no code)."""
    return tools.get_verification_spec()


def main() -> None:
    hosts = [f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"shopco-evidence:{PORT}"]
    import uvicorn

    from .auth import require_token
    app = server.streamable_http_app(host="0.0.0.0", transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts,
        allowed_origins=[f"http://{h}" for h in hosts]))
    uvicorn.run(require_token(app), host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
