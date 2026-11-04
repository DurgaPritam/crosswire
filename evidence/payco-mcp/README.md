# payco-evidence MCP server (Phase 4)

Python, official MCP SDK, **streamable HTTP**, its own Docker service on port 7101. It mounts **only** PayCo's private volume, read-only. payco-agent reaches it through `workspace/payco/.mcp.json`.

| Tool | Returns (never values) |
|---|---|
| `list_failed_deliveries(since_minutes=1440)` | `[{event_id, status, ts}]` |
| `get_delivery_fingerprint(event_id, salt)` | wirecheck fingerprint of the exact bytes PayCo sent |
| `summarize_failures(since_minutes=1440)` | failed vs ok counts grouped by which fields are `non_ascii` (PayCo's half of the clue) |
| `get_signing_spec()` | algorithm, header format, what bytes are signed |

Tests: after `just simulate`, no tool output contains any customer name.
