# notary: deterministic Switch protocol agent (Phase 5)

A custom agent that speaks Switch's agent protocol directly. **No LLM.** Owned by `host`. Read `../switch/docs/official/internals/agent-protocol.md` before building.

## Protocol checklist
- [x] One-time registration (`just notary-register`): **`POST /agents`** with the registration token as bearer, `connection_model: "always_on"`, name `notary`. (`register-known` only accepts known *provider* kinds such as `claude-code`; `always_on` is a connection model, which only the lower-level `POST /agents` takes.) Saves `{id, api_key}` to `.credentials.json` (gitignored, mode 600). **The API key is returned once.** Not run yet: the token must be minted by `host` (Phase 7).
- [x] One persistent connection id (UUID), reused across reconnects (reopening a live id is a takeover).
- [x] `GET /agents/{id}/events?connection_id=…&scope=all&filter=addressed` (SSE). Read `connection_state` first and take rooms and cursor from it. Handle `gap`, `evicted`, `subscription_changed`. Reconnect with `Last-Event-ID` and backoff.
- [x] Heartbeat every 2 s with the connection id and cursor.
- [x] Discover operations with `GET /agents/{id}/ops`. Call `POST /agents/{id}/ops/{name}` with the `X-Switch-Connection-Id` header and unwrapped args.
- [x] Bridge base URL ≠ Gateway URL: probe `GET /health`.

## Behaviour
- `compare <D-id-1> <D-id-2>`: `read_context` → find both disclosures → parse the fingerprint JSON → check the salts match → `wirecheck.compare` → reply in-thread with a table (path | PayCo bytes | ShopCo bytes | delta | match | escaped) and "First difference: <path>, delta <n> bytes." **Never speculates about causes.**
- `help`: lists its commands.
- Missing, malformed or mismatched-salt disclosures: replies with the exact problem.

## Disclosure format it parses
~~~
[D-PAY-3 · approved by @priya]
type: delivery_fingerprint
event: evt_0042
salt: inc-0001-7f3a
```json
{ ...wirecheck fingerprint... }
```
~~~

Tests: parsing, comparison output, reconnect against a fake SSE server.

## Build notes (Phase 5)
- `notary/` = `client.py` (HTTP: health, ops, beat, stream URL), `sse.py` (incremental SSE parser), `agent.py` (connection
  loop + behaviour), `disclosures.py`, `report.py`, `register.py`. State (connection id, cursor, answered message ids)
  lives in `.state.json` (gitignored, mode 600), so a restart reuses the connection id and never answers twice.
- Declares `protocol=1&protocol_accepts=1` (the server, switch-core 0.31.0, speaks 9 and accepts down to 1). Revision 1 is
  the SSE contract in the docs; revision 2+ adds the incarnation fence on every beat and room request.
- `scope=all` connections claim no room, and `post_message` needs one, so the Notary calls `connect_to_room` for the
  event's room before replying.
- Bridge on this machine: `http://127.0.0.1:50675` (Console's local server; probe `/health`, the port can change). From a
  container: `http://host.docker.internal:50675` (checked reachable).
- Run: `just notary` (venv) or `docker compose --profile notary up -d notary`. Tests: `neutral/notary/tests` (parsing,
  table output, reconnect/replay/eviction/heartbeat against a fake bridge, registration).
- **Live pass check pending:** register (needs `host`'s registration key), add the Notary to a test room, post two
  disclosures and `@notary compare D-PAY-1 D-SHOP-1`, then kill/restart it.
