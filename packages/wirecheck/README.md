# wirecheck: privacy-preserving payload fingerprints (Phase 4)

Used by both evidence servers and the notary. Python, typed, pytest.

## API
`fingerprint(raw: bytes, salt: str, event_id: str) -> dict`
```json
{
  "event_id": "evt_0042",
  "total_bytes": 214,
  "sha256": "<HMAC-SHA256(salt, raw) hex>",
  "fields": [
    {"path": "data.customer.name", "offset": 87, "length": 15,
     "hash": "<HMAC of raw slice>", "non_ascii": true, "escaped": true}
  ]
}
```
- A position-tracking JSON scanner: offsets and lengths refer to the **raw** bytes (string slices include quotes). Leaf fields only.
- `non_ascii`: the decoded value has non-ASCII characters. `escaped`: the raw slice contains `\uXXXX`.
- Salted with HMAC so hashes compare across companies within one incident but are useless outside it.

`compare(fp_a, fp_b) -> dict`: total byte delta, whole-body match, per-path rows `{path, len_a, len_b, delta, hash_match, escaped_a, escaped_b}`, and the first differing path. **No values anywhere.**

## Required tests
- An ASCII payload: everything matches.
- "José", provider bytes vs consumer bytes: only `data.customer.name` differs, delta **+4**, `escaped_a=true`, `escaped_b=false`.
- A property test: no output string ever contains any input field value.

## Notes
- Hashes are the first 32 hex chars (128 bits) of HMAC-SHA256(salt, bytes): enough to compare, short enough to post.
- Paths: dotted object keys, `[i]` for array items (`items[0].sku`).
- `delta = len_a - len_b`, with `a` = provider (PayCo) and `b` = consumer (ShopCo): +4 per non-ASCII character
  (`\u00e9`, 6 bytes, vs UTF-8 `é`, 2 bytes).
- Limitation: the salt is posted in the incident room, so anyone in the room could brute-force a low-entropy field
  (a country code) from its hash. Both companies already hold the same payment data; outsiders aren't in the room.
