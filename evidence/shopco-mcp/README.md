# shopco-evidence MCP server (Phase 4)

Python, official MCP SDK, **streamable HTTP**, its own Docker service on port 7102. It mounts **only** ShopCo's private volume, read-only. shopco-agent reaches it through `workspace/shopco/.mcp.json`.

| Tool | Returns (never values) |
|---|---|
| `list_signature_failures(since_minutes=1440)` | `[{event_id, ts}]` |
| `get_verification_fingerprint(event_id, salt)` | wirecheck fingerprint of the exact bytes ShopCo verified over |
| `get_verification_spec()` | prose description of what ShopCo's verifier does (no code) |

**Deliberately missing:** no non-ASCII summary. ShopCo's realistic logs contain no names, so it can't see that correlation. Only PayCo can. This keeps the information split that makes the incident need both sides.

Tests: after `just simulate`, no tool output contains any customer name.

## Build notes
- MCP Python SDK **2.x** (`mcp.server.mcpserver.MCPServer`; FastMCP was renamed in 2.0). Streamable HTTP at
  `http://localhost:7102/mcp`, DNS-rebinding protection on (allowed hosts: localhost, 127.0.0.1, the service name).
- Tool logic is in `shopco_evidence/tools.py` (pure functions over a read-only SQLite connection); `server.py` only wires
  them to MCP. The container runs as `nobody`, with the volume mounted `:ro` and the DB opened `mode=ro`.
- Tests: `evidence/tests/test_evidence.py` (fixture DBs built with the companies' own serializers, plus a live test
  that calls every tool over MCP after `just up && just simulate`).
