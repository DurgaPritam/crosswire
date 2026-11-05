"""payco-evidence MCP server (streamable HTTP). Mounts only PayCo's private volume, read-only."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from . import tools

DB = os.environ.get("PAYCO_DB", "/data/payco/deliveries.db")
DOCS = os.environ.get("PAYCO_DOCS", "/docs/webhooks.md")
PORT = int(os.environ.get("PORT", "7101"))

server = MCPServer(
    "payco-evidence",
    instructions="PayCo's evidence about webhook deliveries. Every answer is counts, event ids, "
                 "byte offsets/lengths and salted hashes: never payload values or customer data.",
)


@server.tool()
def list_failed_deliveries(since_minutes: int = 1440) -> list[dict[str, Any]]:
    """Webhook deliveries whose latest attempt in the window got a non-2xx response (or no response)."""
    with tools.connect_ro(DB) as db:
        return tools.list_failed_deliveries(db, since_minutes)


@server.tool()
def get_delivery_fingerprint(event_id: str, salt: str) -> dict[str, Any]:
    """wirecheck fingerprint of the exact bytes PayCo sent for one event, salted with the incident salt."""
    with tools.connect_ro(DB) as db:
        return tools.get_delivery_fingerprint(db, event_id, salt)


@server.tool()
def summarize_failures(since_minutes: int = 1440) -> dict[str, Any]:
    """Failed vs ok deliveries grouped by which JSON fields contain non-ASCII text (no values)."""
    with tools.connect_ro(DB) as db:
        return tools.summarize_failures(db, since_minutes)


@server.tool()
def get_signing_spec() -> dict[str, Any]:
    """How PayCo signs webhooks: algorithm, header format, and which bytes are signed."""
    return tools.get_signing_spec(DOCS)


def main() -> None:
    hosts = [f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"payco-evidence:{PORT}"]
    import uvicorn

    from .auth import require_token
    app = server.streamable_http_app(host="0.0.0.0", transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts,
        allowed_origins=[f"http://{h}" for h in hosts]))
    uvicorn.run(require_token(app), host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
