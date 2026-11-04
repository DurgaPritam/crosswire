# PayCo (webhook provider): source of PayCo's repo

`just setup` copies this folder to `workspace/payco/` and runs `git init` there. That copy is `payco-agent`'s working directory, and its own git repo.

| Path | Built in | What |
|---|---|---|
| `api/` | Phase 2 | FastAPI service that sends signed `payment.succeeded` webhooks |
| `docs/webhooks.md` | Phase 2 | PayCo's public webhook docs (slightly ambiguous on purpose) |
| `AGENT.md` | kit | Runtime playbook; becomes `CLAUDE.md` and `AGENTS.md` in the workspace |
| `.mcp.json` | Phase 6 | Connects payco-evidence (http://localhost:7101/mcp) |
| `.claude/settings.template.json` | Phase 6 | Permissions and hooks; `just setup` renders it to `.claude/settings.json` per machine (never committed) |
| `hooks/disclosure_guard.py`, `hooks/path_guard.py` | Phase 6 | Installed by `just setup` from the canonical `guards/` (never edit them in the workspace) |

Key spec:
- Body = `json.dumps(event, separators=(",", ":"))` with default `ensure_ascii`, so `é` is sent as `\u00e9`.
- Header `PayCo-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, f"{t}.{body}")>`.
- Every delivery (exact bytes, signature, status) goes into a **private** SQLite db in a Docker volume (`/data/payco/deliveries.db`), never in this folder.
- Amounts are integer cents. No number-like keys.
