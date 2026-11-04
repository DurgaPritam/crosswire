# reference-fixes (Phase 2)

The correct fixes, as patches. Used **only** by `just verify-fixed`, which applies them to a temporary copy and checks that 60/60 events pass. They're never applied to `workspace/`; in the demo, the agents write their own fixes.

- `shopco-raw-body.patch`: keep the raw request bytes through the queue and verify over them.
- `payco-regression-test.patch`: a non-ASCII fixture and a docs clarification ("signature is computed over the exact raw request body bytes").
