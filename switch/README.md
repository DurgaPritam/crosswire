# Setting up Switch for Crosswire

Click-by-click setup. Claude Code adds `crosswire.template.yaml` in Phase 7.5 and refines this guide.

## 1. Users and identities (Gateway)
1. Create Switch users `priya`, `sam` and `host` (`host` = admin; owns the mediator and notary).
2. Create matching Mattermost accounts and **link (claim) each one to its Switch user**. Unlinked accounts match nobody in addressing rules.
3. For recording: two browser profiles, Priya and Sam.

## 2. Agents (Console)
| Agent | Provider | Working dir | Owner |
|---|---|---|---|
| `payco-agent` | Claude Code | `workspace/payco` | `priya` |
| `shopco-agent` | Claude Code | `workspace/shopco` | `sam` |
| `mediator` | Claude Code | `workspace/mediator` | `host` |
| `notary` | custom (`neutral/notary`) | n/a | `host` |

VERIFY: the registering user becomes the owner. Keep **bypass permissions off**.

## 3. Addressing policies (Console: Your Agents → agent → Who can talk to your agent)
| Agent | Rule | Rooms | Users | Agents |
|---|---|---|---|---|
| `payco-agent` | 1 | `#payco-internal` | `owner` | none |
| | 2 | `#payco-shopco-shared` | `owner` | `mediator` |
| `shopco-agent` | 1 | `#shopco-internal` | `owner` | none |
| | 2 | `#payco-shopco-shared` | `owner` | `mediator` |
| `mediator` | 1 | `#payco-shopco-shared` | `*` | `payco-agent`, `shopco-agent`, `notary` |
| `notary` | 1 | `#payco-shopco-shared` | `*` | `mediator` |

Once an agent has any rule, everything not admitted is denied, and a refused message gets a visible reply.

## 4. Rooms, roles, links
Create these rooms:
- `#payco-internal`: Priya and `payco-agent`
- `#shopco-internal`: Sam and `shopco-agent`
- `#payco-shopco-shared`: Priya, Sam, and all four agents. Paste `shared-room-instructions.md` into its instructions field.

Then:
- **Roles** in the shared room: `incident-commander` (exclusive), `provider-responder`, `consumer-responder`, `notary`. Ask each agent to take its role, and check with `!roles`.
  - An agent can hold **one role at a time, across all rooms**.
- **Links:** link both internal rooms to the shared room.

## 5. Smoke test
- [ ] `!list-documents` and `!roles` work in the shared room
- [ ] Priya → `@payco-agent hello` works. Sam → `@payco-agent hello` gets a **visible refusal**.
- [ ] `@notary help` replies
- [ ] `@mediator who are you and what is this room for?` gets a room-specific answer
