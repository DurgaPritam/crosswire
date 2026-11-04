# ShopCo (webhook consumer): source of ShopCo's repo

`just setup` copies this folder to `workspace/shopco/` and runs `git init` there. That copy is `shopco-agent`'s working directory, and its own git repo.

| Path | Built in | What |
|---|---|---|
| `app/` | Phase 2 | Express receiver, SQLite job queue, worker (**the bug lives here**) |
| `app/lib/signature.js` | Phase 2 | `verifySignature(payload, header, secret)`: ordinary-looking code |
| `AGENT.md` | kit | Runtime playbook; becomes `CLAUDE.md` and `AGENTS.md` in the workspace |
| `.mcp.json` | Phase 6 | Connects shopco-evidence (http://localhost:7102/mcp) |
| `.claude/settings.json` | Phase 6 | Permissions and the disclosure-guard hook |
| `hooks/disclosure_guard.py` | Phase 6 | Blocks code, secrets, names, unapproved disclosures |

Key spec:
- `POST /webhooks/payco` uses `express.json()`, enqueues `{event_id, payload: req.body, signature_header}` and returns 202. Raw bytes are **not** kept (realistic fast-ack design).
- The worker verifies over `` `${t}.${JSON.stringify(job.payload)}` `` (raw `é`, 2 bytes), so a mismatch happens **only** for non-ASCII names.
- Logs contain only `event_id=<id> signature=ok|mismatch`, **never names**.
- A private `verify_audit(event_id, bytes, ok)` table in the Docker volume `/data/shopco/jobs.db` stores the exact bytes verified over (read only by shopco-evidence).
