# PayCo webhooks

PayCo notifies your server about payment activity by sending an HTTPS `POST` with a JSON
body to the endpoint you register in the dashboard.

## Events

| Type | When |
|---|---|
| `payment.succeeded` | A payment was captured |

Example body (pretty-printed here for readability):

```json
{
  "id": "evt_0042",
  "type": "payment.succeeded",
  "created": 1762300800,
  "data": {
    "amount_cents": 4200,
    "currency": "EUR",
    "customer": { "id": "cus_0042", "name": "Jane Doe", "country": "FR" }
  }
}
```

Amounts are always integers in the currency's minor unit (cents).

## Verifying signatures

Every request carries a `PayCo-Signature` header:

```
PayCo-Signature: t=1762300800,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

- `t` is the Unix timestamp at which PayCo signed the request.
- `v1` is a hex-encoded HMAC-SHA256, keyed with your endpoint's signing secret.

The signature is computed over the JSON payload, prefixed with the timestamp and a dot:

```
signed_payload = t + "." + payload
v1 = hex(HMAC_SHA256(secret, signed_payload))
```

To verify, compute the same HMAC with your secret and compare it to `v1` using a
constant-time comparison. We recommend rejecting requests whose `t` is more than five
minutes old.

## Responding

Return any `2xx` status to acknowledge receipt. PayCo records the response status of
every delivery attempt; non-`2xx` responses (for example `401` when your signature check
fails) show up as failed deliveries.
