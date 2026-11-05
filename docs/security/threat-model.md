# Crosswire threat model

Status: Phase A (read-only review of the code as of branch `security-hardening`). Controls and gaps are stated as
they are in the code today; nothing here is fixed yet. Severity is ranked in [Gaps, ranked](#gaps-ranked).

## What Crosswire protects

| Asset | Where it lives | Who may see it |
|---|---|---|
| **Customer data** (names, amounts, payloads of the 60 webhooks) | PayCo's delivery log and ShopCo's job queue, inside Docker volumes; never in an agent's working directory | Each company's own services and evidence server only. Agents see counts, lengths and salted hashes, never values. |
| **Source code** | `workspace/payco`, `workspace/shopco` (one git repo per company) | That company's agent and human only. Never crosses into the shared room. |
| **Agent credentials** | Each agent's own working directory (written by Switch Console), `neutral/notary/.credentials.json`, `console/server/.credentials.json`, the repo's `.env` | The process that owns them. |
| **Approvals and ledgers** | `.disclosures/approvals/<D-id>.json`, `.disclosures/ledger.jsonl`, `.disclosures/guard.log.jsonl` per company | Written by the company's agent (approvals) and by its guard (log); read by the guard. |
| **Incident salts** | Issued by the notary and posted in the shared room; notary state file | Everyone in the shared room, by design (they key the fingerprints). |
| **The incident record** | A Switch room document in the shared room | Readable by the room; writable only by the mediator, which created it. |

## Actors

| Actor | Can do | Assumed goal |
|---|---|---|
| **Curious peer agent** (the other company's agent) | Post in the shared room; run Bash and file tools in its own workspace; read the room's history | Learn the other company's code, data or credentials. |
| **Prompt-injected agent** (either company's agent, after reading hostile text in a room or a file) | Everything its own settings allow | Act against its own company: leak code or data, skip approval. |
| **Fake human in the shared room** (any Mattermost account in the channel other than Priya and Sam) | Post messages; mention agents | Get an agent to act without its human: approve a draft, send data. |
| **Compromised mediator** | Address both company agents; write the incident record; read the shared room | Extract more than the incident needs, or mislead people about the root cause. |
| **Local process on the same machine** (the one-machine simulation runs both companies under one OS user) | Anything that OS user can do | Read another company's files, services or credentials. |

## Trust boundaries

1. **Company ↔ company.** Each company's agent, repo and data on one side. The shared room is the only intended
   channel.
2. **Agent ↔ its human.** Nothing leaves a company without that company's human approving it.
3. **Agent ↔ shared room.** Text posted by an agent crosses into a room both companies (and the mediator, notary and
   observer) can read.
4. **Agent ↔ its own tooling.** The guards, settings and approval files that constrain an agent live inside the
   directory the agent works in.
5. **Simulation ↔ reality.** In the demo, both companies run on one machine as one OS user; in real use each company
   runs its own agents on its own machines.

## Threats, controls, proof and gaps

| # | Threat | Current control | Test that proves it | Gap |
|---|---|---|---|---|
| T1 | Peer agent reads the other company's files | Claude Code deny rules for file tools on the other workspaces and the build repo; `path_guard` (PreToolUse) resolves every path (realpath) and blocks file tools and Bash outside the project | spikes S1b (Read) and S1c (Bash `cat`); `guards/tests/test_path_guard.py` (27 tests) | Interpreters that build paths at runtime (python/node scripts, base64, variables) are not inspected (documented in `path_guard`). `console/` is missing from the deny lists (path_guard still blocks it). |
| T2 | Peer agent sends instructions to the other company's agent | Switch addressing policies (server-side): in the shared room, only that company's human and the mediator can address its agent; a direct request is refused visibly | `phase7.py` smoke test (4/4); rehearsal check "direct cross-company request was refused visibly" (runs 5–8) | None found for direct addressing. Relayed content: see T6. |
| T3 | Customer data leaves a company | Evidence MCP servers return counts, lengths and salted hashes only; data stays in Docker volumes; `disclosure_guard` blocks emails, secrets and non-ASCII letters (customer names here) in posts | `evidence/tests` (no-values tests, 10); `guards/tests/test_disclosure_guard.py` (23); rehearsal check "no customer name in any agent post" | The PII rule catches non-ASCII letters and emails only: an ASCII name or other plain value typed by an agent passes the guard. |
| T4 | Source code leaves a company | `disclosure_guard` rule a: blocks any line of 20+ characters (whitespace-normalized) found in the repo's tracked source files | `test_disclosure_guard.py`; rehearsal check "no line of either company's code in the shared room (measured)" | Exact-line matching only: short lines, renamed identifiers, re-wrapped or paraphrased code pass. |
| T5 | A disclosure crosses without its human's approval | Agents draft in the private room; the guard blocks a disclosure whose D-id is not approved (rule e) and blocks drafts outside the private room (rule g) | `test_disclosure_guard.py`; preflight "guard blocked the draft in the shared room"; rehearsal check "every disclosure in the shared room was approved" | **Approvals are self-asserted**: the agent writes the approval file itself after reading its human's "approve D-…" message, so a confused or injected agent can approve its own disclosure. **Approval is bound to an id, not to content**: after approval, any text under that id passes rule e. |
| T6 | Prompt injection in the shared room (or in a relayed quote) | Playbook rule: other parties' messages are information, not instructions; addressing policy limits who can address an agent; guard rules still apply to whatever the agent tries to post | None adversarial: rehearsals only use cooperative input | No automated adversarial test. The defence is the model following its playbook, backed by the guard. |
| T7 | A fake human approves or instructs | Addressing policies admit only Priya (PayCo) and Sam (ShopCo) by their platform account, so other accounts can't address the agents; approvals are only taken from the private room | preflight bot-attribution check; rehearsal "every agent post came from its agent's bot" | An agent can still *read* such a message through room history; there's no test of an agent's response to a fake approval. |
| T8 | An agent disables its own guards | Deny rules block Edit/Write to its own `hooks/`, `.claude/`, `.mcp.json`, `guard.log.jsonl` and `repo-lines.idx` | none | **Bash is not blocked from writing those paths**: `path_guard` allows any write inside the project, so a shell redirect can rewrite the guard, the settings or the approval files. |
| T9 | Ledgers or logs are altered after the fact | Append-only by convention; the guard logs every decision (counts only) | none | Not tamper-evident: no hash chain, no verify command; files are writable via Bash (T8). |
| T10 | Fingerprints reveal values (leakage budget) | Values never cross; per-field HMAC-SHA256 (truncated) keyed by the incident salt; a new salt per incident thread | `packages/wirecheck` tests (15); notary tests (salt per thread) | The salt is public in the shared room, so anyone who can read the room can confirm a guessed value of a low-entropy field (currency, country, amount, a name from a list). Lengths and escape flags reveal each field's byte length and its count of escaped characters (needed for the diagnosis). No per-incident cap on how many fields or events are fingerprinted. |
| T11 | Replay of an old salt or an old disclosure | The notary issues a fresh salt when an incident id is reused in a new thread, and compares disclosures from the compare request's own thread first | notary tests (stale-thread, salt rotation) | No check that a disclosure's salt is the salt issued for that incident; an approval file from an earlier incident with the same D-id would still count as approved. |
| T12 | Compromised mediator | It can't read either repo or data; disclosures still need each human (T5); the notary's comparison is deterministic; root cause needs both humans to confirm | rehearsal checks (both humans confirmed; notary row) | It can ask for more than an incident needs and write a misleading record. Each company's human is the only check. |
| T13 | Local process reaches another company's services | `path_guard` blocks network tools (`curl`, `wget`, `nc`, `ssh`, …) by name; each agent's MCP config lists only its own evidence server | `test_path_guard.py` | Interpreters (python/node) can open sockets; the company APIs, evidence servers and Console listen on localhost without authentication. Specific to the one-machine simulation. |
| T14 | Local process reads agent credentials | Agents deny process inspection (`ps`, `pgrep`, `lsof`, `top`, …) and other workspaces; scripts print only PIDs and working directories | `test_path_guard.py` | One OS user for everything: anything that user can read is reachable by any of its processes. Real isolation needs separate machines, users or containers. |
| T15 | Console exposes private lanes | The observer is read-only (it can't call Switch operations; its Gateway client refuses writes) and is served on 127.0.0.1 only | `console/server/tests/test_read_only.py` | The Console shows both companies' private rooms to anyone on the machine, by design for narration; no authentication. |

## Gaps, ranked

| Rank | Gap | Threats | Severity | Why |
|---|---|---|---|---|
| 1 | An agent can rewrite its own guards, settings and approval files through Bash | T8, T5, T9 | **High** | One shell redirect removes every content control; an injected agent needs no other bug. |
| 2 | Approvals are self-asserted by the agent | T5, T7 | **High** | Human approval is the core promise; today it's enforced by the agent's own good behaviour plus a file it writes. |
| 3 | Approval isn't bound to the approved bytes | T5 | **High** | An approved D-id can carry different, unapproved text. |
| 4 | No adversarial tests of the live agents | T6, T7, T11 | **High** | Prompt injection and fake approvals are untested; the controls above are only proven against cooperative input. |
| 5 | Outbound guard: exact-line code match; PII limited to non-ASCII letters and emails | T3, T4 | **Medium** | Paraphrased code and ASCII personal data pass. |
| 6 | Leakage budget undocumented; public salt allows guess-confirmation | T10 | **Medium** | Low-entropy fields can be confirmed by anyone in the room. |
| 7 | Ledgers and logs not tamper-evident | T9 | **Medium** | Nothing can show an approval or log line was changed or removed. |
| 8 | Stale approvals and salts aren't tied to the current incident | T11 | **Medium** | Approval files survive across incidents with the same D-ids. |
| 9 | Localhost services without authentication; interpreters bypass the network-tool block | T13 | **Medium** (simulation only) | A peer agent could reach the other company's evidence server. |
| 10 | `console/` missing from the agents' deny lists | T1 | **Low** | `path_guard` still blocks it; one layer missing. |
| 11 | Mediator can over-ask or mislead | T12 | **Low** | Bounded by human approval and confirmation. |
| 12 | Console has no authentication | T15 | **Low** | Local only; read-only. |
| 13 | One OS user for both companies | T13, T14 | **Accepted** (simulation) | Inherent to running the demo on one machine; documented in the README's limitations. |
