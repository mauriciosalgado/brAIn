# Orders API reference

Tags: #api #reference

## Create an order

`POST /v1/orders`

```bash
curl -sS -X POST https://api.example.com/v1/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @order.json
```

### Request body

```json
{
  "customer": { "id": "c_1001", "email": "dara@example.com", "tier": "gold" },
  "items": [
    { "sku": "KB-001", "qty": 2, "unit_price": 49.9, "tax": { "rate": 0.19, "code": "DE-VAT" } },
    { "sku": "MS-014", "qty": 1, "unit_price": 19.5, "tax": { "rate": 0.19, "code": "DE-VAT" } },
    { "sku": "HD-220", "qty": 3, "unit_price": 7.25, "tax": { "rate": 0.07, "code": "DE-VAT-R" } },
    { "sku": "CB-777", "qty": 10, "unit_price": 1.15, "tax": { "rate": 0.19, "code": "DE-VAT" } },
    { "sku": "PW-050", "qty": 1, "unit_price": 89.0, "tax": { "rate": 0.19, "code": "DE-VAT" } },
    { "sku": "LP-900", "qty": 1, "unit_price": 1299.0, "tax": { "rate": 0.19, "code": "DE-VAT" } },
    { "sku": "SP-310", "qty": 4, "unit_price": 12.0, "tax": { "rate": 0.19, "code": "DE-VAT" } }
  ],
  "shipping": {
    "method": "express",
    "address": {
      "line1": "Musterstrasse 12",
      "line2": "Hinterhaus",
      "city": "Berlin",
      "postal_code": "10115",
      "country": "DE"
    },
    "notes": "Leave at the back door. Ring twice. The dog is friendly but loud. Do not leave with neighbours."
  },
  "payment": { "method": "card", "token": "tok_example_123", "currency": "EUR", "capture": true },
  "metadata": { "source": "web", "campaign": "spring-sale", "referrer": "newsletter", "experiment": "checkout-v3" }
}
```

### Response codes

| Code | Meaning | Retry |
|------|---------|-------|
| 201 | Order created | no |
| 400 | Validation failed, see `errors[]` | no |
| 409 | Duplicate `Idempotency-Key` | no |
| 429 | Rate limited, see `Retry-After` | yes |
| 503 | Temporary outage | yes, with backoff |

## Get an order

`GET /v1/orders/{id}`

Returns the order with its current status. Statuses are `pending`, `paid`, `shipped`, `delivered`, `cancelled`.
