# ShopCo (webhook consumer): source of ShopCo's repo

`just setup` copies this folder to `workspace/shopco/` and runs `git init` there. That copy is `shopco-agent`'s working directory, and its own git repo.

| Path | Built in | What |
|---|---|---|
| `app/` | Phase 2 | Express receiver, SQLite job queue, worker (**the bug lives here**) |
| `app/lib/signature.js` | Phase 2 | `verifySignature(payload, header, secret)`: ordinary-looking code |
| `AGENT.md` | kit | Runtime playbook; becomes `CLAUDE.md` and `AGENTS.md` in the workspace |
| `.mcp.json` | Phase 6 | Connects shopco-evidence (http://localhost:7102/mcp) |
| `.claude/settings.template.json` | Phase 6 | Permissions and hooks; `just setup` renders it to `.claude/settings.json` per machine (never committed) |
| `hooks/disclosure_guard.py` | Phase 6 | Blocks code, secrets, names, unapproved disclosures |

Key spec:
- `POST /webhooks/payco` uses `express.json()`, enqueues `{event_id, payload: req.body, signature_header}`, then waits up to `VERDICT_WAIT_MS` (3 s) for the worker's verdict: **401** on a mismatch, otherwise 202. Raw bytes are **not** kept (queue-first design). The short wait is what lets PayCo see failures as 401s (its half of the clue); verification itself stays in the worker.
- The worker verifies over `` `${t}.${JSON.stringify(job.payload)}` `` (raw `é`, 2 bytes), so a mismatch happens **only** for non-ASCII names.
- Logs contain only `event_id=<id> signature=ok|mismatch`, **never names**.
- A private `verify_audit(event_id, bytes, ok)` table in the Docker volume `/data/shopco/jobs.db` stores the exact bytes verified over (read only by shopco-evidence).
