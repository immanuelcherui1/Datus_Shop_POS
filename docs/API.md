# HTTP API

Base path: `/api`. JSON requests; Decimal quantities and amounts are **strings**. Unknown fields are rejected. Authentication uses an HttpOnly cookie. After login, copy the readable `csrf_access_token` cookie into `X-CSRF-TOKEN` for POST/PUT requests. The frontend does this automatically.

Every posting endpoint below requires `Idempotency-Key: <unique 8–100 character value>` except login, logout and quote. Keep the same key and payload when retrying. Success is 200; validation is 400, authentication 401, permission 403, unavailable/out-of-scope record 404, stock/idempotency/uniqueness conflict 409, temporary database failure 503.

List endpoints generally return `{items, total, pages}` and accept `page` and `size` (maximum 100). `/users` is a simple array. GET endpoints never mutate stock or financial history.

| Method | Path | Permission / purpose |
|---|---|---|
| GET | `/health` | Local service/database health |
| POST | `/auth/login` | username/password; rate limited |
| POST | `/auth/logout` | Invalidate this user's sessions and clear cookies |
| GET | `/auth/me` | User, branch, role, permissions and business configuration |
| GET | `/products?q=...` | Authenticated catalogue for current branch |
| POST | `/products` | catalog |
| PUT | `/products/{id}` | catalog; complete validated product document |
| GET | `/inventory/movements?product_id=...` | catalog |
| POST | `/inventory/adjustments` | adjust |
| GET | `/inventory/reconciliation` | adjust |
| GET / POST | `/suppliers` | purchase |
| GET / POST | `/purchases` | purchase |
| POST | `/purchases/{id}/receipts` | purchase |
| POST | `/sales/quote` | sell; calculates current totals, no posting |
| GET / POST | `/sales` | sell; report roles can read; cashier sees own sales |
| GET | `/sales/{id}` | Receipt snapshot; own sale restriction for cashiers |
| POST | `/sales/{id}/returns` | refund |
| GET | `/register` | register; open session or null |
| POST | `/register/open` | register |
| POST | `/register/close` | register; adjustment authority for variances |
| GET | `/reports/daily?date=YYYY-MM-DD` | report; configured business timezone |
| GET / POST | `/users` | users (owner) |
| GET | `/audit` | audit |

## Examples

Create product:

```json
{"sku":"RICE-1KG","barcode":"6001234567890","name":"Rice 1kg","category":"Food","unit":"bag","retail_price":"180.00","wholesale_price":"2040.00","pack_size":"12","tax_rate":"0","reorder_level":"12","active":true}
```

Create a purchase (quantities and costs are per base unit):

```json
{"supplier_id":1,"lines":[{"product_id":1,"quantity":"24","unit_cost":"130.00"}]}
```

Receive part of a purchase:

```json
{"lines":[{"line_id":1,"quantity":"12"}]}
```

Quote:

```json
{"customer":"Walk-in customer","lines":[{"product_id":1,"quantity":"2","mode":"retail","discount":"0"}]}
```

Checkout (assuming the quote is 360):

```json
{"customer":"Walk-in customer","lines":[{"product_id":1,"quantity":"2","mode":"retail","discount":"0"}],"payments":[{"method":"cash","amount":"360.00","reference":null}]}
```

Opening adjustment:

```json
{"product_id":1,"quantity":"24","unit_cost":"130.00","reason":"Verified opening stock count"}
```

Partial cash return:

```json
{"reason":"Customer returned unopened bag","lines":[{"line_id":1,"quantity":"1","disposition":"restock"}],"refunds":[{"payment_id":1,"amount":"180.00","reference":null}]}
```

Register open/close:

```json
{"opening":"1000.00"}
```

```json
{"counted":"1360.00","notes":"Drawer reconciled"}
```

Use actual IDs returned by your database. The examples describe payload shape, not preinstalled records. No API permits deleting posted records, editing movements, overwriting balances, or accepting unverified provider success.

## 0.3.0 amendments

- `GET/POST /api/catalogue-options`: saved category/unit labels (catalog permission).
- `POST /api/inventory/transfers`: `{product_id, quantity: "2", unit: "pack", reason}`; wholesale to retail, adjustment permission, idempotent.
- Products expose `retail_quantity`, `wholesale_quantity`, total `quantity`, `inventory_value`, `cost_per_unit`, `cost_per_pack`. `sort=stock` prioritizes low quantities; `low=1` filters low active products.
- Product input adds `packaging_unit` and optional ISO `expiry_date`.
- `PUT /api/suppliers/{id}` updates contact/details; create/update rejects duplicate names.
- Purchase input adds `status` (`draft` or `ordered`) and line `purchase_unit` (`unit` or `pack`). `unit_cost` is per selected unit. `PUT /api/purchases/{id}` edits/confirms drafts only. Receipt quantities remain base units; optional receipt-line `unit_cost` records actual base-unit cost.
- Cart modes: `wholesale` (pack), `wholesale_unit`, `retail` (unit), `retail_pack`. Mixed channels are rejected. Existing settlement method identifiers remain unchanged.
- Sales GET filters: `user_id`, `type`, `method` (`cash`, `external_mobile`, `other`), `start`, `end`. Cashiers still see only their own sales. Responses include operator/channel/payment details.
- Register open adds `opening_mpesa`; close adds `counted_mpesa`. `notes` remains the API field behind **Remarks**. `GET /api/register/history` returns both reconciliations and actors.
- `GET /api/reports/insights?start=YYYY-MM-DD&end=YYYY-MM-DD`: business-timezone range, maximum 367 inclusive days; current inventory health and range activity.

All mutations retain the existing `Idempotency-Key`, authentication, CSRF and permission rules. Prices and costs are decimal strings. See [AMENDMENTS.md](AMENDMENTS.md).
