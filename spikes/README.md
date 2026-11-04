# Phase 0 spikes: results

Record PASS/FAIL and notes here. Later phases read this file.

| # | Test | How | Result | Notes / fallback chosen |
|---|---|---|---|---|
| S1 | Directory isolation | Ask spike agent A to read `../agent-b/secret-b.txt` → must be refused | ☐ | Fail → container isolation (stretch 11.7); meanwhile separate repos + deny rules |
| S2 | Addressing | Agent A owner-only; agent B @mentions A → **visible refusal** from Switch | ☐ | Fail → stop, ask in Discord (design depends on it) |
| S3 | Hooks in Console sessions | Agent A (run by Console) posts "BLOCKME test" → blocked by hook | ☐ | Fail → outbox + poster process instead of a hook |
| S4 | Room hop | Agent A in `spike-private` uses `connect_to_room` to `spike-shared`, posts, reconnects | ☐ | **PASS → Plan A, FAIL → Plan B** (edit the AGENT.md files) |
| S5 | Room documents | A creates a doc; B can read it but can't update it | ☐ | Fail → mediator posts the record as a pinned message |

**Approval plan chosen:** ☐ Plan A ☐ Plan B

Reminders:
- New agents start **owner-only**; **unlinked chat accounts match nobody**. Link your Mattermost account to your Switch user first.
- Keep **bypass permissions off**.
