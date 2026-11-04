# payco-evidence MCP server (Phase 4)

Python, official MCP SDK, **streamable HTTP**, its own Docker service on port 7101. It mounts **only** PayCo's private volume, read-only. payco-agent reaches it through `workspace/payco/.mcp.json`.

| Tool | Returns (never values) |
|---|---|
| `list_failed_deliveries(since_minutes=1440)` | `[{event_id, status, ts}]` |
| `get_delivery_fingerprint(event_id, salt)` | wirecheck fingerprint of the exact bytes PayCo sent |
| `summarize_failures(since_minutes=1440)` | failed vs ok counts grouped by which fields are `non_ascii` (PayCo's half of the clue) |
| `get_signing_spec()` | algorithm, header format, what bytes are signed |

Tests: after `just simulate`, no tool output contains any customer name.

## Build notes
- MCP Python SDK **2.x** (`mcp.server.mcpserver.MCPServer`; FastMCP was renamed in 2.0). Streamable HTTP at
  `http://localhost:7101/mcp`, DNS-rebinding protection on (allowed hosts: localhost, 127.0.0.1, the service name).
- Tool logic is in `payco_evidence/tools.py` (pure functions over a read-only SQLite connection); `server.py` only wires
  them to MCP. The container runs as `nobody`, with the volume mounted `:ro` and the DB opened `mode=ro`.
- Tests: `evidence/tests/test_evidence.py` (fixture DBs built with the companies' own serializers, plus a live test
  that calls every tool over MCP after `just up && just simulate`).
