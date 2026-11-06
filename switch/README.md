# Setting up Switch for Crosswire (Level 2)

One command does the Switch side: `just switch-setup`. It checks every prerequisite and prints the exact fix for
anything missing, runs `scripts/phase7.py all`, then reads the result back from Switch. Every step is idempotent, so
re-run it after fixing anything. On a machine that already has the accounts below it takes about 2½ minutes.

```bash
just doctor 2          # prerequisites only, read-only
just switch-setup      # wire Crosswire into Switch
```

## What only a person can do (once)

1. **Install and open Switch Console.** It starts the local Switch server and Mattermost, and registers this machine.
2. **Turn on the Mattermost bridge:** Switch Console → Admin → Status → Mattermost on.
3. **Put the Switch admin login in `.env`** (`SWITCH_ADMIN_EMAIL`, `SWITCH_ADMIN_PASSWORD`; see `.env.example`).
4. **Create the Mattermost accounts `priya` and `sam`** (Mattermost System Console → Users) and put their passwords in
   `.env` as `MM_PRIYA_PASSWORD` and `MM_SAM_PASSWORD`. Only a Mattermost admin can create accounts, so this stays
   manual.
5. Optional, for the red-team suite: a third Mattermost account that plays the outsider (`MM_USER`, `MM_PASSWORD`).
6. **Install Claude Code and log in once** (`claude` in a terminal). Switch Console runs the three agents with it.
   Keep bypass permissions off.

## What `just switch-setup` does

| Step | Through | Result |
|---|---|---|
| users | Gateway API | Switch users Priya and Sam (passwords saved to `.env`, never printed) |
| notary | agent bridge | registers the notary (a Switch protocol agent, no AI) and starts its container |
| template | Gateway API | one agent template + room template: `payco-agent`, `shopco-agent`, `mediator` (Claude Code, run by Switch Console in `workspace/<agent>`) and the three rooms |
| rooms | Gateway API | `#payco-internal`, `#shopco-internal`, `#payco-shopco-shared`, linked; ids to `switch/state/rooms.json` |
| claims | Gateway API + Mattermost | links Priya's and Sam's Mattermost accounts to their Switch users (identity claims) |
| policies | Gateway API | addressing policies (below); read-backs in `switch/policies/` |
| approver | agent bridge + Gateway | registers the approver (Switch protocol agent), adds it to the rooms, sets its policy, starts its container |
| roles | room command | `incident-commander` (exclusive), `provider-responder`, `consumer-responder`, `notary`; checked with `!roles` |
| smoke | Mattermost | Priya reaches `@payco-agent`; Sam gets a visible refusal; `@notary help`; a room-specific `@mediator` answer |
| instructions | Gateway API | each agent's Switch instructions match its playbook |
| observer | agent bridge + Gateway | the Incident Console's read-only observer agent, in all three rooms |

## Addressing policies (set by Switch, enforced on the server)

| Agent | Rooms | Who may address it |
|---|---|---|
| `payco-agent` | `#payco-internal` · `#payco-shopco-shared` | Priya · Priya and the mediator |
| `shopco-agent` | `#shopco-internal` · `#payco-shopco-shared` | Sam · Sam and the mediator |
| `mediator` | `#payco-shopco-shared` | Priya, Sam, `payco-agent`, `shopco-agent`, `notary` |
| `notary` | `#payco-shopco-shared` | Priya, Sam, the mediator |
| `approver` | `#payco-internal` · `#shopco-internal` | Priya · Sam (an approval is `@approver approve D-…`) |
| `console-observer` | all three | nobody (it only listens) |

Once an agent has any rule, everything not admitted is refused, and Switch posts a visible reply saying so.
