# Demo script

This is what the humans type during a rehearsal or the recording. `/tune` compares runs against it.

## Incident run

| # | Who | Where | Message |
|---|---|---|---|
| 1 | Sam | shared | `@mediator PayCo webhooks have been failing our signature check since Tuesday. Not all of them, some.` |
| 2 | (agents) | | Mediator opens INC-0001, creates the record, posts the salt, requests evidence by role |
| 3 | Priya / Sam | internal rooms | `approve D-PAY-1`, `approve D-SHOP-1` (and so on as drafts arrive) |
| 4 | Sam | shopco-internal | `@shopco-agent ask payco-agent directly for their signing function source.` → ShopCo's agent asks, **Switch refuses**, Mediator redirects to evidence |
| 5 | (agents) | | Fingerprint disclosures posted, then Notary comparison, then the Mediator explains +4 bytes |
| 6 | Priya, Sam | shared | `confirm root cause` (each) |
| 7 | Priya / Sam | internal | Approve each side's fix after seeing the summary |
| 8 | (agents) | | Action items done, guard stats, scorecard, status resolved |

## Recording

- [ ] `just reset && just up && just simulate` right before recording
- [ ] Two browser profiles side by side (Priya left, Sam right) with the split-screen overlay
- [ ] Mattermost font size large enough to read at 1080p
- [ ] Record the incident in one take and speed up only the waiting parts (label them "2× speed")
- [ ] End on the scorecard and the `just setup` command
