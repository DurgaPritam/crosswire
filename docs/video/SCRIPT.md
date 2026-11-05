# Demo video script (2:42; hard cap 3:00)

DRAFT. The main stage is the Incident Console replaying the best clean rehearsal
(`console/fixtures/demo-run.events.jsonl`) in presentation mode (press **P**). Picture-in-picture cuts show the real
Mattermost chat whenever a person acts. Replay timestamps (`@m:ss`) are filled in from the chosen run before
recording.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00–0:05 | `video-01-title.png` | Crosswire. Two companies debug one bug without sharing code. |
| 0:05–0:17 | `video-02-problem.png` | PayCo's signed webhooks fail at ShopCo, only for customers with accented names. Each side's code looks right, and neither will share it. |
| 0:17–0:27 | Console, presentation mode, replay start: three lanes | Each company has its own agent, with its own repo. They meet in a shared Switch room, run by a neutral mediator. |
| 0:27–0:37 | PiP: Sam's report in Mattermost → "INC-0001 · investigating", salt posted | Sam reports it. The mediator opens an incident, and the notary issues a salt. |
| 0:37–0:53 | PayCo lane: draft "Awaiting Priya" → PiP: Priya approves → the card crosses the seam | Agents draft; people approve. Only counts, field paths and salted hashes ever leave a company. |
| 0:53–1:13 | **Proof: the refusal.** Red seam flash, lock, toast "Switch refused · shopco-agent → payco-agent · not_permitted", the refused message | ShopCo's agent asks PayCo's agent directly. Switch refuses it, on the server. Every cross-company request goes through the mediator. |
| 1:13–1:28 | **Proof: the boundary.** View as PayCo: ShopCo's lane frosts over, "ShopCo private · you can't see this" | This is PayCo's view. ShopCo's lane isn't blurred on screen; its content never reaches PayCo at all. |
| 1:28–1:53 | **Proof: the byte diff.** Notary compare → modal: `data.customer.name`, PayCo vs ShopCo bytes, "+N bytes", "escaped" | The notary compares both fingerprints, field by field. Every field matches but one: the customer's name. PayCo's copy is longer. |
| 1:53–2:03 | `video-03-byte-gap.png` (José: 9 bytes vs 5) | PayCo signs é as an escape, six bytes. ShopCo verifies raw UTF-8, two. The signature can't match. |
| 2:03–2:13 | PiP: Priya and Sam reply "confirm root cause" → status "root cause agreed" | Both people confirm the root cause. |
| 2:13–2:25 | 2× label. Private lanes: tests pass; PiP: both fix approvals | Each side fixes its own code and runs its own tests. |
| 2:25–2:36 | Finale: "INC-0001 resolved", hero tile "Lines of code shared 0", tiles | Resolved. Every disclosure approved, one request refused, zero lines of code shared. |
| 2:36–2:42 | `video-04-closing.png` + `just console-replay` | Built on Switch. Replay it yourself in a minute. |

**Running time: 2:42** (18 s buffer under the 3:00 cap). Voiceover 193 words (about 1:20 of speech at a calm 145 wpm); the rest is on-screen
proof with room to breathe. Cut order if a take runs long: shorten 0:17–0:27 and 2:03–2:25 first. Never trim the three
**Proof** beats.

**Rules for the edit:**
- Label every sped-up segment "2×" on screen. The Console does this in replay.
- Every number spoken must match the replayed run (minutes to root cause, disclosure count, bytes). Read them off the
  finale before recording the voiceover.
- No customer names or payload values on screen, except José on the explainer frame (it's a design frame, not data).
