# mediator: working directory source

Contains only the playbook (`AGENT.md`) and, from Phase 6, a locked-down `.claude/settings.json` (no network tools, nothing outside this folder, only `python3 -c` for the salt). The mediator has **no code and no data access** by design. `just setup` copies this to `workspace/mediator/`, with `AGENT.md` becoming `CLAUDE.md`.
