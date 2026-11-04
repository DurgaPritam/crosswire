# notary: deterministic Switch protocol agent (Phase 5)

A custom agent that speaks Switch's agent protocol directly. **No LLM.** Owned by `host`. Read `../switch/docs/official/internals/agent-protocol.md` before building.

## Protocol checklist
- [ ] One-time registration: `POST /agents/register-known` with the Gateway registration token as bearer, `agent_type: "always_on"`, name `notary`. Save `{id, api_key}` to `.credentials.json` (gitignored, mode 600). **The API key is returned once.**
- [ ] One persistent connection id (UUID), reused across reconnects (reopening a live id is a takeover).
- [ ] `GET /agents/{id}/events?connection_id=…&scope=all&filter=addressed` (SSE). Read `connection_state` first and take rooms and cursor from it. Handle `gap`, `evicted`, `subscription_changed`. Reconnect with `Last-Event-ID` and backoff.
- [ ] Heartbeat every 2 s with the connection id and cursor.
- [ ] Discover operations with `GET /agents/{id}/ops`. Call `POST /agents/{id}/ops/{name}` with the `X-Switch-Connection-Id` header and unwrapped args.
- [ ] Bridge base URL ≠ Gateway URL: probe `GET /health`.

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
