# Demo video script (target 2:45, hard cap 3:00)

DRAFT. The main stage is the Incident Console replaying the best clean rehearsal
(`console/fixtures/demo-run.events.jsonl`) in presentation mode (press **P**). Picture-in-picture cuts show the real
Mattermost chat whenever a person acts. Replay timestamps (`@m:ss`) are filled in from the chosen run before
recording.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00–0:08 | `video-01-title.png` | Crosswire. Two companies debug an integration together without sharing code. |
| 0:08–0:25 | `video-02-problem.png` | PayCo sends signed webhooks. ShopCo rejects some of them, only for customers with accented names. Each side's code looks right. Neither will paste production data into the other's chat. |
| 0:25–0:38 | Console, presentation mode, replay at the start: three lanes, empty incident | Each company has its own AI agent, with its own repo and logs. They meet in a shared Switch room, run by a neutral mediator. |
| 0:38–0:50 | PiP: Mattermost, Sam's report in #shopco-internal → Console: "INC-0001 · investigating", salt posted | Sam reports the failures. The mediator opens an incident. A neutral notary hands out a salt, so fingerprints only compare inside this incident. |
| 0:50–1:08 | PayCo lane: a draft card "Awaiting Priya" → PiP: Priya types "approve D-PAY-1" → the card crosses the seam | Agents draft. People approve. Nothing leaves a company until its human says yes, and what leaves is counts, field paths and salted hashes. No values. |
| 1:08–1:25 | 2× replay label. The refusal: red seam flash, lock, toast "Switch refused · shopco-agent → payco-agent" | ShopCo's agent tries to ask PayCo's agent directly. Switch refuses it, on the server. Cross-company requests go through the mediator. |
| 1:25–1:38 | View as **PayCo**: the ShopCo lane frosts over ("ShopCo private · you can't see this") | This is what PayCo sees. ShopCo's lane isn't hidden by the screen. It never reaches PayCo at all. |
| 1:38–1:58 | Notary compare → byte diff modal: `data.customer.name`, PayCo vs ShopCo bytes, "+N bytes" counts up, "escaped" | The notary compares the two fingerprints byte by byte. One field differs: the customer's name. PayCo's copy is longer. |
| 1:58–2:10 | `video-03-byte-gap.png` (José: `4A 6F 73 5C 75 30 30 65 39` vs `4A 6F 73 C3 A9`) | Here's why. PayCo signs é as an escape, six bytes. ShopCo re-serializes the JSON and verifies over é as raw UTF-8, two bytes. Four bytes per accented character, so the signature fails. |
| 2:10–2:22 | PiP: Priya and Sam each reply "confirm root cause" → Console status turns to the seam gradient, "root cause agreed" | Both people confirm the root cause. The mediator writes an action item for each side into the incident record. |
| 2:22–2:35 | 2× label. Private lanes: tests passing; PiP: approvals of both fixes | Each agent fixes its own side, in its own repo, and runs its own tests. Each human approves the merge. |
| 2:35–2:48 | Finale: "INC-0001 resolved", hero tile "Lines of code shared 0", tiles (root cause in N min, disclosures all approved, 1 refusal by Switch) | Resolved. Every disclosure approved. One request refused by Switch. Zero lines of code shared. |
| 2:48–2:58 | `video-04-closing.png` + `just console-replay` | It runs on Switch: rooms, server-enforced addressing, room documents, roles and two custom protocol agents. Clone it and replay this incident in a minute. |

**Rules for the edit:**
- Label every sped-up segment "2×" on screen. The Console does this in replay.
- Every number spoken must match the replayed run (minutes to root cause, disclosure count, bytes). Read them off the
  finale before recording the voiceover.
- No customer names or payload values on screen, except José on the explainer frame (it's a design frame, not data).
