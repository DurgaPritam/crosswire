<p align="center"><img src="docs/design/banners/readme-banner.png" alt="Crosswire" width="640"></p>

<h3 align="center">Two companies' AI agents debug a cross-company outage together,<br>without either side seeing the other's code or customer data.</h3>

<p align="center">
  <a href="https://github.com/DurgaPritam/crosswire/actions/workflows/ci.yml"><img src="https://github.com/DurgaPritam/crosswire/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/built%20on-Switch-8A7CF0" alt="Built on Switch">
  <img src="https://img.shields.io/badge/Flip%20the%20Switch-Best%20Business%20Workflow-2BB5A5" alt="Flip the Switch: Best Business Workflow">
  <img src="https://img.shields.io/badge/red%20team-14%2F14%20blocked-E8735A" alt="Red team: 14 of 14 live attacks blocked">
</p>

<p align="center">
  <b><a href="VIDEO_URL">▶ 3-minute demo video</a></b> ·
  <b><a href="https://crosswire-plum.vercel.app/">Watch a real incident replay in your browser</a></b> ·
  <a href="#how-crosswire-uses-switch">How we use Switch</a> ·
  <a href="https://crosswire-plum.vercel.app/?view=security">Try to break it</a> ·
  <a href="#run-it">Run it yourself</a>
</p>
<!-- TODO: replace VIDEO_URL once the video is uploaded -->

<p align="center"><img src="docs/screenshots/console-switch-labels.png" alt="The Incident Console during run 20: PayCo's private room, the shared room and ShopCo's private room side by side, every post tagged with the Switch feature that carried it"></p>

<p align="center"><sub>Run 20, 2 minutes 39 seconds in. Every post carries a <b>SWITCH</b> tag naming the feature that produced it: the private room it stayed in, the role it was addressed to, the approver's signature, the room document only the mediator can edit.</sub></p>

## In one real run

The hosted replay plays rehearsal run 20 from start to finish, as it happened. These are the numbers it ended with:

| ⏱ Incident time | 🔎 Root cause agreed | 📤 Disclosures | ⛔ Refused by Switch | 🧾 Lines of code shared |
|:---:|:---:|:---:|:---:|:---:|
| **12 min 27 s** | **5 min** | **8, all approved by a person** | **1** | **0** (measured) |

## The problem

PayCo sends signed webhooks to ShopCo. ShopCo rejects some of them, but only for customers with accented names.

Each side's code looks correct on its own. The bug only shows up when you compare what PayCo signed with what ShopCo
verified, and neither company will paste production payloads, code or customer names into the other company's chat.
So a bug like this usually takes a week of emails, a shared spreadsheet and a lot of trust.

Crosswire runs that investigation as a live incident in team chat. Each company's AI agent investigates at home, a
neutral mediator runs the incident, and nothing leaves a company unless that company's on-call engineer approves it.
**Switch does all of the coordination**: who is in which room, who may talk to whom, who approved what, and where the
record lives.

## The cast

| | Who | Kind | What they do |
|:---:|---|---|---|
| <img src="docs/design/avatars/avatar-priya-512.png" width="40" alt=""> | **Priya** · PayCo on-call | Person, in Mattermost | Approves every PayCo disclosure and PayCo's fix |
| <img src="docs/design/avatars/avatar-sam-512.png" width="40" alt=""> | **Sam** · ShopCo on-call | Person, in Mattermost | Reports the failures; approves every ShopCo disclosure and ShopCo's fix |
| <img src="docs/design/avatars/avatar-payco-agent-512.png" width="40" alt=""> | **payco-agent** | Claude Code, run by Switch Console | Investigates PayCo's side with evidence tools; drafts disclosures; fixes PayCo's repo |
| <img src="docs/design/avatars/avatar-shopco-agent-512.png" width="40" alt=""> | **shopco-agent** | Claude Code, run by Switch Console | The same for ShopCo |
| <img src="docs/design/avatars/avatar-mediator-512.png" width="40" alt=""> | **mediator** | Claude Code, run by Switch Console | Incident commander: opens the incident, keeps the record, routes every cross-company request |
| <img src="docs/design/avatars/avatar-notary-512.png" width="40" alt=""> | **notary** | Switch protocol agent, no AI | Issues the per-incident salt and compares the two fingerprints byte by byte |
| ✍️ | **approver** | Switch protocol agent, no AI | Signs an approval only when Priya or Sam gives it, in their own room |
| 👁 | **console-observer** | Switch protocol agent, read-only | Feeds the Incident Console and the rehearsal grader |

## How a Crosswire incident works

![Each company's agent works in its private room with its own evidence tools; only approved, salted fingerprints cross into the shared room, where the mediator runs the incident and the notary compares bytes](docs/design/diagram/crosswire-architecture-1600x900.png)

1. **Sam reports the failures** in the shared room, from Mattermost. The mediator opens incident INC-0001 as a Switch
   room document that only it can edit. The notary issues a per-incident salt.
2. **Each company's agent investigates privately**, in its own room, with evidence tools that return counts, lengths
   and salted hashes, never values.
3. **Agents draft, people approve.** Each draft ends with its exact approve command, and Priya or Sam replies with it
   in their private room: `@payco-agent @approver approve D-PAY-1`. The approver signs it, and only then can the
   disclosure cross into the shared room.
4. **ShopCo's agent asks PayCo's agent directly, and Switch refuses it** on the server, with a visible reply.
   Cross-company requests go through the mediator.
5. **The notary compares the two fingerprints field by field.** `data.customer.name` differs by 4 bytes per accented
   character: PayCo signs `é` as the escape `\u00e9` (6 bytes), and ShopCo re-serializes it to raw UTF-8 (2 bytes)
   before verifying.
6. **Both people confirm the root cause.** Each agent fixes its own side in its own repo and runs its own tests, and
   each person approves the merge. The incident is resolved.

![The notary's byte comparison: every field matches except data.customer.name, which is longer on PayCo's side and escaped](docs/screenshots/byte-diff.png)

## How Crosswire uses Switch

**This is the core of the project.** Without Switch, "the agents only talk through the mediator" or "only Priya can
approve" would be lines in a prompt that a clever message could talk an agent out of. With Switch they're decisions
the server makes before a message is delivered. Every beat of the incident depends on a Switch feature:

| Beat in the incident | Switch feature | What Switch does | Where |
|---|---|---|---|
| Sam and Priya work from Mattermost | **Mattermost bridge + identity claims** | People stay in the chat tool they already use. Each Mattermost account is claimed by a Switch user, so policies know who is speaking | [`scripts/phase7.py`](scripts/phase7.py) (`users`, `claims`) |
| Three rooms: one per company and a shared one | **Rooms + room links** | `#payco-internal` and `#shopco-internal` are private. Both are linked to `#payco-shopco-shared` | [`switch/crosswire.template.yaml`](switch/crosswire.template.yaml) |
| The mediator asks "`@provider-responder`, send a fingerprint" | **Roles** | Agents address a role, not a name. `incident-commander` is exclusive, so there is only ever one | [`switch/crosswire.template.yaml`](switch/crosswire.template.yaml) |
| INC-0001's status, symptoms, hypotheses and action items | **Room documents** | The incident record lives in the shared room. Only the mediator, which created it, can edit it | [`neutral/mediator/AGENT.md`](neutral/mediator/AGENT.md) |
| ShopCo's agent tries to instruct PayCo's agent | **Addressing policies, enforced on the server** | Only Priya and the mediator may address payco-agent (Sam and the mediator for shopco-agent). Anything else is refused, and Switch says so in the room | [`switch/policies/`](switch/policies/) |
| Priya approves `D-PAY-1` | **Addressing policy + custom protocol agent** | Switch delivers `@approver approve …` as *addressed* only when it comes from Priya in `#payco-internal` (Sam in `#shopco-internal`). The approver signs only addressed messages, so an approval from anyone else never reaches it | [`approver/approver/switch_watch.py`](approver/approver/switch_watch.py), [`switch/policies/approver.json`](switch/policies/approver.json) |
| The salt, and the byte-by-byte comparison | **Custom protocol agent** | The notary is deterministic Python with no model, speaking Switch's agent protocol directly | [`neutral/notary/`](neutral/notary/) |
| payco-agent, shopco-agent and the mediator | **Console-managed agents + agent and room templates** | One template creates the three Claude Code agents and three rooms. Switch Console runs each agent in its own working directory | [`switch/crosswire-team.template.yaml`](switch/crosswire-team.template.yaml) |
| The Incident Console and the grader | **Read-only protocol agent** | `console-observer` reads the rooms with `get_room_detail` and `read_context` only. The grader reads the incident **through Switch**, not the chat platform's API, so a clean run proves Switch carried the whole conversation | [`console/server/`](console/server/), [`scripts/switch_read.py`](scripts/switch_read.py) |
| Setting all of it up | **Gateway API** | `just switch-setup` creates users, the template, rooms, claims, policies and roles, then reads them back from Switch | [`scripts/switch_setup.py`](scripts/switch_setup.py) |

<details>
<summary><b>The Switch surface Crosswire touches</b></summary>

- **Gateway API (admin):** users, agent and room templates, rooms and room links, identity claims, addressing
  policies, agent instructions, collaborations (to check the Mattermost bridge is on).
- **Agent protocol (the notary, the approver, the observer):** an SSE stream per agent (`/agents/{id}/events`,
  `scope=all`), heartbeats, and the operations `list_rooms`, `get_room_detail`, `read_context`, `connect_to_room` and
  `post_message`. The observer is limited to the two read operations in code, and anything else is refused before a
  request is sent.
- **Room commands:** `!roles` to check role holders, and `!reset @agent` to give every agent a fresh context before
  a rehearsal.
- **Switch Console:** runs the three Claude Code agents, each with its own deny rules, hooks and OS sandbox.

</details>

### Architecture

```mermaid
flowchart TB
  subgraph PEOPLE["People, in Mattermost"]
    direction LR
    Priya(["Priya · PayCo on-call"])
    Sam(["Sam · ShopCo on-call"])
  end

  subgraph SW["Switch server"]
    direction LR
    RP["#35;payco-internal<br/>PayCo only"]
    RSH["#35;payco-shopco-shared<br/>incident record = room document"]
    RS["#35;shopco-internal<br/>ShopCo only"]
    RP -. "room link" .- RSH
    RSH -. "room link" .- RS
  end

  subgraph AI["Claude Code agents, run by Switch Console"]
    direction LR
    PA["payco-agent<br/>role: provider-responder"]
    MED["mediator<br/>role: incident-commander"]
    SA["shopco-agent<br/>role: consumer-responder"]
  end

  subgraph PROTO["Protocol agents, no AI"]
    direction TB
    APP["approver<br/>signs Priya's and Sam's approvals"]
    NOT["notary<br/>salt + byte comparison"]
    OBS["console-observer<br/>read-only: Console + grader"]
  end

  subgraph EV["Evidence MCP servers, Docker"]
    direction LR
    PE[("PayCo evidence")]
    SE[("ShopCo evidence")]
  end

  PEOPLE -- "Mattermost bridge + identity claims" --> SW
  SW <-- "addressing policies, enforced on the server" --> AI
  SW <-- "agent protocol: SSE down, HTTP up" --> PROTO
  PA -- "counts, lengths, salted hashes only" --> PE
  SA -- "counts, lengths, salted hashes only" --> SE

  classDef payco stroke:#E8735A,stroke-width:2px
  classDef shopco stroke:#2BB5A5,stroke-width:2px
  classDef neutral stroke:#8A7CF0,stroke-width:2px
  class Priya,RP,PA,PE payco
  class Sam,RS,SA,SE shopco
  class RSH,MED,APP,NOT,OBS neutral
  style SW fill:transparent,stroke:#8A7CF0,stroke-width:2px
  style PEOPLE fill:transparent,stroke:#888,stroke-dasharray:4 4
  style AI fill:transparent,stroke:#888,stroke-dasharray:4 4
  style PROTO fill:transparent,stroke:#888,stroke-dasharray:4 4
  style EV fill:transparent,stroke:#888,stroke-dasharray:4 4
```

## What enforces what

| Guarantee | Enforced by | Strength |
|---|---|---|
| ShopCo can't instruct PayCo's agent (and vice versa) | Switch addressing policies naming the allowed people and the mediator (server-side; agents can't widen their own) | Hard |
| Only Priya (or Sam) can approve their company's disclosures | Switch delivers an approval to the approver only from that person in that company's room; the approver also checks the sender | Hard |
| Company agents can't edit the incident record | Switch: only the creating agent can edit a room document | Hard |
| Agents never see raw payloads or names | Evidence MCP servers run in Docker; private data is never mounted into agent directories | Hard |
| Agents can't read the other company's code | Claude Code deny rules and `path_guard` for file tools, and an OS sandbox around every agent's shell (the working directory alone is not a boundary: see [Proof](#how-we-know-it-works)) | Strong |
| A disclosure crosses only with a valid approval | The approver signs only an approval bound to that draft's evidence, the current incident and the notary's salt; the disclosure guard checks the signature at posting time | Strong |
| Agents can't switch off their own guards | Guards, settings and playbooks are pinned by hash and immutable; the guards and the approver refuse to work if anything changed | Strong |
| No code, secrets or personal data posted to Switch | The `disclosure_guard` hook on every Switch post tool (code lines even with renamed identifiers, secrets, emails, customer names) | Medium |

## Run it

Three levels, so you can stop at whichever proves enough. Start with `just doctor`: it checks the prerequisites for
every level and prints the exact fix for anything missing. It's read-only.

```bash
git clone https://github.com/DurgaPritam/crosswire.git && cd crosswire
just doctor
```

### Level 0 · Replay a real incident (no Switch, Docker or Claude)

Or skip the install entirely: **[the hosted replay](https://crosswire-plum.vercel.app/)** is the same thing, in your
browser. Locally you need Python 3.11+, Node 20+ and [`just`](https://github.com/casey/just).

```bash
just console-replay           # http://127.0.0.1:7300 plays rehearsal run 20
```

Press **P** for presentation mode. Use **View as PayCo** to see only what PayCo sees: ShopCo's lane is frosted, and
its content never reaches the page. Replays play at 1×, 2× or 4×. When the incident resolves, **Postmortem** opens the
shared report built from what both companies saw.

### Level 1 · Reproduce the bug and the fix (Docker, no agents)

Needs Docker and Node 22+.

```bash
just setup && just up && just simulate
just verify-bug               # exactly the 6 webhooks with non-ASCII names fail
just verify-fixed             # with the reference fixes applied: 60/60
just test                     # every suite
```

### Level 2 · The full live incident on your own Switch Console

One command takes a running Switch Console to 6 agents, 3 rooms, 4 roles, addressing policies and identity claims,
then reads the result back from Switch. Every step is idempotent.

```bash
just switch-setup
just console                  # Live mode: press "Run live incident"
```

Or rehearse from the terminal with `.venv/bin/python scripts/rehearse.py --runs 1`: a preflight (agents, policies,
tools, sandbox, fresh contexts), then a full incident played by scripted Priya and Sam, graded on 17 checks.

**The steps only a person can do, once** (we'd rather list them than hide them):

1. Install and open Switch Console. It starts the local Switch server and Mattermost, and registers the machine.
2. Turn on the Mattermost bridge: Switch Console → Admin → Status → Mattermost on.
3. Put the Switch admin login in `.env` (`SWITCH_ADMIN_EMAIL`, `SWITCH_ADMIN_PASSWORD`; see [`.env.example`](.env.example)).
4. Create the Mattermost accounts `priya` and `sam`, and put their passwords in `.env`. Only a Mattermost admin can
   create accounts.
5. Optional, for the red-team suite: a third Mattermost account that plays the outsider.
6. Install Claude Code and log in once. Keep bypass permissions off.

The details, and the addressing policy for each agent, are in [`switch/README.md`](switch/README.md).

**Cold start**, measured on a clean GitHub Actions Ubuntu runner: Level 0 replay **26 s**, `just test` **35 s**,
Level 1 **100 s**.

## How we know it works

![The finale of run 20: INC-0001 resolved, 0 lines of code shared (measured), 8 disclosures all approved, 1 refusal by Switch, both fixes merged](docs/screenshots/finale-run20.png)

- **Three consecutive clean live runs on the final code** (rehearsal runs 19, 20 and 21), each a full incident end to
  end with no human input beyond scripted Priya and Sam. Run 21 was started through the Incident Console's **Run live
  incident** action. Run 22, after the last playbook fix, was also clean, on all 17 checks.
- **The 17 checks include:** every disclosure in the shared room was approved, the direct cross-company request was
  refused visibly by Switch, the notary's first difference is `data.customer.name`, no customer name in any agent post,
  no line of either company's code in the shared room (measured against both repos), every ledger intact and every
  disclosure signed (`just verify-ledger`), and the grader read the incident through Switch.
- **Guard stats from runs 20–22:** the disclosure guards checked 26–38 posts per agent per run and blocked 1–2 per
  agent: preflight's deliberate test of the room rule, and disclosures that added unapproved prose around the approved
  evidence block. 0 lines of repo code were posted.
- **The working directory is not a boundary.** In spike S1, Console's default auto mode let one agent read a sibling
  agent's folder with no prompt. Isolation is therefore enforced by deny rules (S1b), the `path_guard` hook (S1c) and
  an OS sandbox. The spikes are in [`spikes/`](spikes/).
- **Tests:** 344 tests in 11 suites, plus the Console typecheck (`just test`). CI runs `just doctor`, a Level 0 replay
  smoke test, `just test` and the full Level 1 flow on every push.
- **The recording** of run 20 is [`console/fixtures/demo-run.events.jsonl`](console/fixtures/demo-run.events.jsonl):
  the hosted replay plays exactly that file.

## What's real and what's scripted

Priya and Sam are scripted: the rehearsal posts their messages from their own Mattermost accounts, exactly as a person
would through the Switch bridge, and they copy the agents' approve commands literally. Everything else is live: the
three Claude Code agents, the rooms, roles, policies and room document, the notary, the approver's signatures, the
evidence servers and both companies' tests.

## Security

While building Crosswire, our team found a security issue in Switch itself and reported it privately to the Switch
team through GitHub's vulnerability reporting.

## Security architecture

Crosswire is a security product, so it is tested like one. [`docs/security/threat-model.md`](docs/security/threat-model.md)
lists what it protects, who might attack it, 15 threats with their controls and tests, the ranked gaps and the known
limits. The controls, outermost first:

1. **Switch addressing policies.** Server-side; one company's agent can't instruct the other's, and only Priya or Sam
   can reach the approver.
2. **An OS sandbox around every agent's shell.** It writes only inside its own working directory (not its controls),
   reads neither the other workspaces nor the build repo, and has no network.
3. **Immutable, pinned controls.** Guards, settings, MCP config and playbooks are hashed at setup and made immutable;
   the guards fail closed if anything changed.
4. **The approver.** A Switch protocol agent in its own Docker container, with its own signing key. It signs an
   approval only when Switch delivers Priya's or Sam's `approve D-…` to it, bound to that draft's evidence, the current
   incident and the notary's salt. The disclosure guard checks the signature before anything crosses.
5. **The outbound guard.** Code (even with renamed identifiers), secrets, emails and customer names never leave.
6. **Tamper-evident records.** Guard logs and the approver's signed ledger are hash-chained; `just verify-ledger`
   checks them and that every disclosure that crossed was signed. Every rehearsal runs it.
7. **Evidence servers.** Each needs its own company's token and fingerprints at most 5 events per incident salt.
8. **Context isolation.** Each agent loads instruction files only from its own workspace (no parent `CLAUDE.md`, no
   user memory or skills), and starts every rehearsal from a reset context.

**Red-team scorecard** (adversarial messages to the live agents, and each control tested directly):

| | Baseline | After hardening |
|---|---|---|
| Live agents: 14 adversarial scenarios (prompt injection, fake approvals, self-approval, reading the other workspace, disabling a guard, reaching the other evidence server, asking what the agents know about the build, …) | 13 blocked, 1 leaked | **14 blocked** |
| Controls: 10 forbidden actions run straight at the guards and the OS sandbox, as if the model had not refused | 1 blocked, 9 allowed | **10 blocked** |

The baseline's live scenarios were stopped by the model refusing or by Switch's addressing policy. The controls column
shows what stops them when the model doesn't refuse. The one leak, RT14, was added later: the agents had been loading
the build checkout's own instructions from a parent folder, and answered questions about the build from them. Each
agent now loads only its own workspace's instructions, and preflight checks it.

<p align="center"><a href="https://crosswire-plum.vercel.app/?view=security"><img src="docs/screenshots/try-to-break-it.png" width="720" alt="Try to break it: 14 of 14 live attacks blocked and 10 of 10 controls held on their own"></a></p>

Every attack is listed with the exact message we sent, on the **[Try to break it](https://crosswire-plum.vercel.app/?view=security)**
page. Run the Console locally and the same page runs your own text through the real disclosure guard. The scorecards are in
[`docs/security/scorecards/`](docs/security/scorecards/).

## Honest limitations

- **It's a one-machine simulation.** Both companies' agents run on the same laptop under the same OS user. In real
  life each company runs its own agents on its own machines.
- **The Switch admin owns all the agents** in the simulation. Policies are written by the admin, not by each company.
- **Both companies share one OS user.** Anything that user can read is reachable by any of its processes, so
  our agents deny process inspection and each other's workspaces. That's a mitigation, not a fix; running each
  company on its own machine or container would close it.
- **Approvals are as strong as Priya's and Sam's Mattermost accounts.** The approver signs what those accounts
  approve; whoever can post as them can approve.
- **Priya and Sam are scripted** in rehearsals. The rooms, policies and agents they talk to are not.

## Repository layout

```
companies/payco/   PayCo's repo (Python API, webhook signer) and its agent's playbook and settings
companies/shopco/  ShopCo's repo (Node app and worker, the verifier) and its agent's playbook and settings
evidence/          the two evidence MCP servers (Docker): counts, lengths and salted hashes, never values
packages/wirecheck fingerprint library used by the evidence servers and the notary
neutral/mediator/  the mediator's playbook
neutral/notary/    the notary: a custom Switch protocol agent (Python, no LLM)
approver/          the approver: a Switch protocol agent with its own signing key and hash-chained ledger (Docker)
guards/            path_guard and disclosure_guard (Claude Code hooks)
switch/            room and agent templates, policy read-backs, shared-room instructions
console/           the Incident Console (Python server + React app) and recorded runs
scripts/           doctor, setup, simulate, Switch wiring (switch_setup.py, phase7.py), preflight, rehearse, red team
reference-fixes/   the correct fixes, used only by `just verify-fixed`
docs/              threat model, scorecards, design assets, screenshots
```

## Built with

Built during **Flip the Switch** (Nov 4–7, 2026) on [Switch](https://github.com/sandbox-quantum/switch) (rooms,
roles, addressing policies, room documents, identity claims, the agent protocol, Console and the Mattermost bridge) ·
[Claude Code](https://claude.com/claude-code) · Claude Design (visual identity and Console design) · Mattermost ·
Docker · Python, Node, React, Tailwind, Framer Motion.
<!-- TODO: team names -->
