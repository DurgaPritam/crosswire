# shopco-evidence MCP server (Phase 4)

Python, official MCP SDK, **streamable HTTP**, its own Docker service on port 7102. It mounts **only** ShopCo's private volume, read-only. shopco-agent reaches it through `workspace/shopco/.mcp.json`.

| Tool | Returns (never values) |
|---|---|
| `list_signature_failures(since_minutes=1440)` | `[{event_id, ts}]` |
| `get_verification_fingerprint(event_id, salt)` | wirecheck fingerprint of the exact bytes ShopCo verified over |
| `get_verification_spec()` | prose description of what ShopCo's verifier does (no code) |

**Deliberately missing:** no non-ASCII summary. ShopCo's realistic logs contain no names, so it can't see that correlation. Only PayCo can. This keeps the information split that makes the incident need both sides.

Tests: after `just simulate`, no tool output contains any customer name.
