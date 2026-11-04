# guards: the canonical PreToolUse hooks for every agent

`just setup` copies these into each agent workspace's `hooks/` on every run (workspace copies are gitignored and
protected by `Edit(.../hooks/**)` deny rules). Edit them only here. Tests: `guards/tests/`.

| Guard | Installed for | What it does |
|---|---|---|
| `path_guard.py` | payco, shopco, mediator (`--mediator`) | Keeps file tools and Bash inside the agent's directory (realpath, `../`, `~`, `$HOME`, `$TMPDIR`, absolute paths, symlinks, globs; `/tmp` blocked). Blocks process inspection and network tools in Bash. `--mediator`: Bash may only run the salt one-liner. Logs to `hooks/path.log`. |
| `disclosure_guard.py` | payco, shopco | On Switch post/document tools: blocks repo source lines, emails, secrets, non-ASCII letters, unapproved disclosures (`DRAFT D-…:` posts allowed), room-document writes. Logs to `.disclosures/guard.log.jsonl` (no text). |

Layering (proven in spikes S1b/S1c and again for `payco-agent` in Phase 6): deny rules are checked **before**
hooks, so they are the file-tool boundary; `path_guard` is the Bash boundary and the backstop for file paths the
deny rules don't list.
