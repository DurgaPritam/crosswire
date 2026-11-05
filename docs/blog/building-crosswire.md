# Two companies, one bug, zero lines of code shared: building Crosswire on Switch

*DRAFT. Written for people trying Switch for the first time. Everything here was done on an Apple-silicon Mac with
Switch Console 0.40.1 and switch-core 0.31.0, in November 2026.*

Crosswire is a hackathon project about a very ordinary kind of bug. PayCo sends signed webhooks. ShopCo, its customer,
rejects some of them. Signatures fail only for customers with accented names. Each company's code looks right on
its own:

- PayCo signs the exact bytes it sends. Python's `json.dumps` escapes `é` as `é` (6 bytes).
- ShopCo's worker gets parsed JSON off a queue and verifies over `JSON.stringify(payload)`, which writes `é` raw
  (2 bytes in UTF-8).

Four bytes per accented character, and the signature is different. In real life this takes a week of emails, because
neither side will paste production payloads, code or customer names into the other's Slack.

In Crosswire, each company has a Claude Code agent with access to its own repo and logs. The two agents debug the
problem in a shared Switch room. Neither side sees the other's code. A neutral mediator agent runs the incident, a
deterministic "notary" agent compares byte fingerprints, and a human on each side approves every piece of evidence
before it leaves the company. This post covers how we built it, including what didn't work.

## 1. Setup, with the real gotchas

Switch Console runs the Switch server (natively or in Docker) plus a Mattermost instance for the chat side. Three
things cost us time:

**Mattermost has no arm64 image.** Console's Mattermost switch fails with `no matching manifest for linux/arm64`. Turn
on Rosetta in Docker Desktop (Settings → General → "Use Rosetta for x86_64/amd64 emulation") and pre-pull:

```bash
docker pull --platform linux/amd64 mattermost/mattermost-team-edition:11.9.0
```

**The Docker credential helper isn't on Console's PATH.** If a pull from Console fails with
`docker-credential-desktop: executable file not found in $PATH`, pre-pull in Terminal. If that isn't enough, back up
`~/.docker/config.json` and remove its `"credsStore"` line.

**The Mattermost switch isn't in Settings.** It's under **Admin → Status**. Its port can also change after a restart,
so check **Home → Mattermost → ⋮ → Sign-in details…** and keep your `MM_URL` in step.

We kept every credential in a gitignored `.env` (mode 600) that scripts load. Env vars exported in one terminal don't
reach a Claude Code session started from an IDE extension.

## 2. Rooms and addressing

We use three rooms: `#payco-internal`, `#shopco-internal`, and `#payco-shopco-shared`. The interesting part is
**addressing policies**, which the server enforces. Each agent has rules that say who may address it, and where:

```json
{ "rooms": ["#payco-shopco-shared"], "users": ["@priya (Mattermost)"], "agents": ["mediator"],
  "room_groups": "*", "owner": false, "owner_agents": false, "platform": false }
```

That is payco-agent's shared-room rule (ids resolved to names; the real read-backs are in `switch/policies/`). Priya
and the mediator can address it there. ShopCo's agent cannot. When shopco-agent asks payco-agent for something
directly, Switch refuses it, and the refusal is visible in the room. That refusal is the demo's turning point. It's
also why Crosswire needs Switch: without server-side addressing, "agents only talk through the mediator" is just a
sentence in a prompt.

Two things we got wrong first:

- **On switch-core 0.31.0, a rule's `users` dimension matches the sender's *platform* account** (the bridge's row for
  the Mattermost user), not the Switch user who claimed it. Claims feed only the `owner` check. Our first policies
  named Switch users and admitted nobody. We now read the accounts from `GET /gateway/collaborations/{bridge}/users`.
- **"No rules at all" means open.** To make a listen-only agent that nobody can address, give it *one rule with every
  dimension empty*, not an empty list.

## 3. The S1 failure: the working directory is not a boundary

Before building anything, we ran five small spikes. Spike S1 asked: can agent A read agent B's files if it's told not
to? It could. Console runs Claude Code in **auto mode**, and auto mode approved
`cat ../agent-b/secret-b.txt` without a prompt. The working directory and `CLAUDE.md` are not a boundary.

So isolation is enforced, in each agent's `.claude/settings.json`, generated per machine from a template:

```json
"deny": ["Read(/{{SHOPCO_DIR}}/**)", "Edit(/{{SHOPCO_DIR}}/**)", "Read(/{{MEDIATOR_DIR}}/**)", "Edit(/{{PROJECT_DIR}}/hooks/**)", ...]
```

There's also a `PreToolUse` hook (`path_guard.py`) for Bash, which deny rules can't express. Two things are worth
knowing:

- **Deny rules run before hooks** for file tools. A deny-rule refusal never reaches your hook, so an empty hook log can
  still mean the check passed.
- **Every agent denies process inspection** (`ps`, `pgrep`, `lsof`, …). On one machine every agent
  runs as the same OS user, so one agent must not be able to inspect another agent's processes.

A second hook, `disclosure_guard.py`, runs on every Switch post. It blocks anything that looks like a raw customer
value, a line from the company's repo, or a draft that hasn't been approved, and it logs counts only.

## 4. The incident record is a room document

Switch's task operations are documented as "present but not ready for use", so we didn't use them. The incident
record is a **room document** that the mediator creates with `create_room_document`. Only the agent that created a
document can update or delete it, and the server enforces that, which is exactly the property we want. The mediator
is the only writer, while everyone in the room can read it with `load_internal_documents`. The record holds the status,
symptoms and a hypotheses table (H1 "signing secret rotated": ruled out; H4 "non-ASCII escaped differently":
supported).

The mediator's playbook has one rule we added after a stale record from a previous run confused it: *an incident
exists only while its record exists.*

## 5. Writing a custom protocol agent

The notary isn't an LLM. It's about 770 lines of Python that speaks Switch's agent protocol directly: SSE down, HTTP up.

```python
# register once (POST /agents with an always_on integration profile), then:
stream = http.stream("GET", f"/agents/{agent_id}/events?connection_id={conn}&scope=all&filter=addressed&protocol=1&protocol_accepts=1")
# ...heartbeat every heartbeat_interval_seconds, and act through operations:
await http.post(f"/agents/{agent_id}/ops/post_message", json={"body": report},
                headers={"X-Switch-Connection-Id": connection_id})
```

When the mediator writes `@notary compare D-PAY-3 D-SHOP-3`, the notary finds both approved disclosures in the
thread, then compares the salted per-field hashes and byte lengths. It replies with a table whose first differing row
reads `data.customer.name | 9 | 5 | +4`. Values never cross. The fingerprints are HMACs under a per-incident salt that
the notary itself posts, so they compare in that room and nowhere else.

Lessons:

- `register-known` only takes provider kinds. A custom agent registers through `POST /agents` with
  `integration_profile.connection_model = "always_on"`.
- A `scope=all` connection claims no room, so call `connect_to_room` before every `post_message`.
- Treat 404 and 409 on a heartbeat as "reopen the stream". Catch errors per message and advance your cursor anyway, or
  one bad message loops forever. (Ours did, once.)
- A `send_targeted_message` arrives with the role mention in front (`@incident-commander [D-SHOP-3 · …]`), so
  parse leniently.

We used the same client for a second protocol agent: the Incident Console's **observer**, which listens with
`filter=all`, admits nobody and never posts.

## 6. Automated rehearsals

A demo with three LLM agents and two humans doesn't work reliably by accident. `scripts/rehearse.py` plays Priya and
Sam through Mattermost's REST API, from Sam's first "signatures are failing" message to both humans confirming the root
cause and approving both fixes. Then it grades the transcript:

```
| every disclosure in the shared room was approved | PASS |
| direct cross-company request was refused visibly | PASS |
| notary table shows data.customer.name +4         | PASS |
| no customer name in any agent post               | PASS |
```

Before every run, a **preflight** checks the things that broke earlier runs:

- stale incident documents;
- roles not held;
- a permission prompt waiting in a room;
- each agent's evidence tool working;
- the guard blocking a draft in the shared room;
- the agents' Switch-stored instructions matching their `AGENT.md`.

That last one was a surprise. A room template copies each agent's instructions into Switch when it creates the
agent, so editing `AGENT.md` afterwards changes nothing until you sync it (`PATCH /gateway/management/agents/{id}`).

The rehearsals found things a single manual run never would:

- an agent stuck on a Bash permission prompt in auto mode;
- a mediator that only woke on addressed messages, while the company agents' plain posts addressed nobody;
- a notary that couldn't parse a targeted message.

Each fix went into a playbook or a guard, never into a "please be careful" sentence.

## What I'd tell a first-time Switch user

- Read `docs/official/internals/identity-and-access.md` before writing policies.
- Prove your isolation with a spike that tries to break it.
- Put anything that has to outlive a session in a room document.
- If a step matters, make a server or a hook enforce it, not a prompt.

The repo has everything needed to replay the incident without Switch: `just console-replay`.
