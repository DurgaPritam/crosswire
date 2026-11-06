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
| T16 | Agents inherit the build context | Claude Code loads `CLAUDE.md` files from every parent directory, and the runtime workspaces sit inside the build checkout, so each agent was given the build assistant's own instructions (plans, dates, internal notes). Each agent's settings now exclude every instruction file outside its workspace (`claudeMdExcludes`), turn auto memory off and deny the `Skill` tool; preflight resets every agent's context (`!reset`) and has it list the instruction files it was given | preflight check (every file inside the workspace); red-team RT14 | The check relies on the agent's own report of its context; Console resumes an agent's last conversation, so a context from before a change persists until it is reset. |

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
| 14 | Agents inherit the build context | T16 | **Medium** (found after the baseline) | An agent could repeat the build assistant's private notes in a room. |

## Status after hardening

Red-team scorecards: [`scorecards/`](scorecards/) (baseline and after). Every fix below passed `just test`, preflight
and a clean live rehearsal (runs 9, 11 and 12).

| Gap | Fix | Proof |
|---|---|---|
| 1 Agent rewrites its own controls | Controls pinned by hash and made immutable; guards fail closed on a mismatch; Bash can't name protected paths or change file attributes; an OS sandbox (writes only in the agent's own directory minus its controls, no reads of other workspaces or the repo, no network) | C01–C04 blocked; preflight canaries DENIED |
| 2+3 Self-asserted approvals, not bound to content | The approver service (Docker, own Ed25519 key) signs only Priya's or Sam's own `approve D-…`, bound to the draft's canonical evidence; the guard verifies the signature and evidence and allows no unapproved prose | C05, C06 blocked; approver tests |
| 8 Stale approvals and salts | The approver signs and serves an approval only for the current incident and the salt the notary issued for it | approver incident-binding tests; C07 blocked |
| 10 `console/` not in deny lists | `console/` and `approver/` denied to every agent | workspace config tests |
| 7 Ledgers not tamper-evident | Hash-chained guard logs and a signed, chained approver ledger; `just verify-ledger` (run by every rehearsal) cross-checks every allowed disclosure | ledger tests; run 12 grader |
| 5 Narrow outbound guard | More secret and credential formats, hashed ASCII customer-name matching, code matching that ignores spacing and renamed identifiers | C08, C09 blocked; 0 false positives replaying 191 recorded agent posts |
| 6 Leakage budget | At most 5 events fingerprinted per incident salt per evidence server | evidence tests |
| 9 Unauthenticated localhost services | A per-company token on each evidence server | preflight: no token or the other company's token gets 401 |
| 14 Build context leaked into agents | `claudeMdExcludes: ["!<workspace>/**"]`, auto memory off, `Skill` denied in every agent's settings; preflight wakes and `!reset`s each agent, then checks the instruction files it reports | RT14 leaked before the fix (both company agents named build-context details), blocked after; preflight check passes |

## Known limits

These remain after the hardening, by decision or because the one-machine simulation can't close them.

| Gap | What remains | Why it stays |
|---|---|---|
| 6 Public salt / leakage budget | Anyone in the shared room holds the incident salt, so a low-entropy field (a country code, a length) can still be confirmed by guessing. Each evidence server now fingerprints at most 5 distinct events per salt, and a new incident gets a new salt. | Comparing fingerprints is the product; a secret salt would need a trusted third party that both companies hash through. |
| 9 Localhost services | Each evidence server now requires its own company's bearer token, and agents can't open sockets (OS sandbox, `WebFetch` denied, MCP config immutable). The company APIs, Mattermost and Switch still listen on localhost, and any process of the same OS user can read the tokens in `switch/state/`. | Real deployments put each company on its own machine or network; see 13. |
| 11 Mediator over-ask | The mediator can still ask for more than an incident needs or write a misleading record. | Every disclosure needs its owner's approval, root cause needs both humans to confirm, and the notary's comparison is deterministic. |
| 12 Console has no authentication | Anyone on the machine can open the Console and see every lane. | It listens on 127.0.0.1 only, is read-only, and exists to narrate the demo. |
| 13 One OS user | Every agent, service and human tool runs as one user. The OS sandbox limits what each agent's shell can touch, but anything outside the sandbox (that user's other processes, Docker) can reach every workspace, the approver's key volume and both ledgers. | Inherent to the demo; real isolation needs separate machines, users or containers. |

Other limits found while hardening:

- **Context isolation is checked by the agent's own report.** Preflight asks each agent which instruction files it was given; settings tests and the RT14 scenario back that up, but nothing reads the model's context directly. The Console's own system prompt and the Switch skill are delivered by design and are not files in the workspace.

- **Reads outside the workspace.** `blockReadsOutsideWorkingDirectories` is not used: with the OS sandbox on, it hangs Claude Code 2.1.299 at startup (bisected). Outside reads are still blocked by the deny rules and `path_guard` for file tools, and by the sandbox's `denyRead` for Bash.
- **What an approval binds.** The approver signs the draft's canonical evidence (D-id, type, event, salt and every JSON block, re-serialised), not its exact bytes: agents re-wrap and re-indent the block when posting (0 of 8 posts matched byte for byte, 8 of 8 matched canonically). To keep unapproved text out, a disclosure post may carry only the evidence block and leading @mentions.
- **Who can approve.** The approver trusts Mattermost user ids. Whoever can post as Priya or Sam can approve, so their accounts are the root of trust.
- **Ledgers.** A hash chain shows a changed, removed or reordered line, and `just verify-ledger` cross-checks the guard logs against the approver's signed ledger. Someone with Docker access could still wipe both. `just reset` deliberately starts both over.
- **Outbound matching.** Names are caught as full or adjacent customer-name tokens; a single first or last name on its own is not, because names like Grace or Young are ordinary words. Code is caught when a line matches exactly or by shape (identifiers renamed, spacing changed); code rewritten in prose or restructured is not.
