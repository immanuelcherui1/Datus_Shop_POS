# Architecture and schema

## Deployment choice

One Windows 11 computer hosts the browser, Waitress/Flask and PostgreSQL. Cash operations need only those local services. The browser has no authority over totals, stock or permissions. Node is needed for building the frontend, not for running the installed application.

An optional backup process reads PostgreSQL using `pg_dump`, encrypts the dump locally, and uploads ciphertext to S3-compatible storage. It never synchronizes active business transactions between databases.

## Relationships

```text
Branch ──< User
Branch ──< CashSession ──< CashMovement >── Payment / Refund
Branch ──< Stock >── Product
Branch ──< Movement >── Product
Supplier ──< Purchase ──< PurchaseLine >── Product
Purchase ──< Receipt ──< Movement
CashSession ──< Sale ──< SaleLine >── Product
Sale ──< Payment
SaleLine ──< Movement
Sale ──< Return ──< ReturnLine >── SaleLine
ReturnLine ──< Movement
Return ──< Refund >── Payment
User ──< Audit
User ──< Idempotency
```

These are physical singular table names generated from the SQLAlchemy models. The exact schema is in `backend/migrations/versions/0001_initial_datus_transaction_schema.py`; migration `0002` installs immutability triggers; `0003` adds allocation caches, purchase snapshots, reusable catalogue options, operator snapshots and M-Pesa session fields. Migrations are frozen snapshots, not `create_all()` calls against changing application models.

The first release intentionally uses one business and one operating branch. `Branch` and branch foreign keys establish record scope and tests prove unauthorized branch records cannot be read. There is no branch-management UI, organization table, multi-tenant onboarding, warehouse transfer engine, or enterprise account provisioning. Product and supplier catalogue records are business-wide; stock and posted operations are branch-scoped.

## Design simplifications

- Roles and permissions are an explicit, version-controlled matrix in `security.py`, not a configurable permission builder.
- Category/unit labels remain compatible strings on products, backed by reusable `CatalogueOption` suggestions (not a hierarchy).
- `Payment` is both a settled-payment record and its allocation to one sale. Multiple rows implement split payment. Partial/credit payment is not accepted.
- `Receipt` is a goods-receipt document. Its immutable movements store the delivered product quantities and values; the purchase lines hold ordered cost and derived received quantity.
- Return quantities are calculated from immutable return lines, not from an editable sold-minus-returned field.
- No double-entry journal is claimed. Gross profit is revenue excluding tax minus recognized cost of goods sold. Damaged returns do not reverse inventory cost.

## Transactions

All posting requests pass through `mutation()`: validate idempotency key, claim it with a unique constraint, run a service, save its JSON response, then commit once. Database, validation and unexpected errors roll back the whole session.

Checkout locks the open register, stock rows sorted by product ID, then product price rows. It calculates current server prices, checks payment equality, captures snapshots, posts stock and cash movements, and writes audit events before commit. Product edits cannot change a price while that product is being finalized.

Receipt posting locks its purchase and sorted stock rows, rejects over-receipt, posts quantity/value, and updates purchase receipt progress. Returns lock the sale, register and stock rows; cumulative amounts are used for partial-refund rounding. Cash closing locks the same session row used by checkout, so closing and selling cannot silently race.

Deadlocks or temporary database errors return a retryable 503 without leaking SQL details. A caller retries the identical request with its original idempotency key.

## Precision and constraints

- Settlement/line totals: `NUMERIC(18,2)`; divided wholesale unit price snapshots: `NUMERIC(18,6)`.
- Quantity and pack conversion: `NUMERIC(18,3)`.
- Stock values and cost snapshots: `NUMERIC(18,6)`.
- Tax rate: fractional `NUMERIC(7,4)` (0.16 means 16%).
- Rounding: decimal half-up per sale line for currency; six decimals for inventory value.
- Input limits reject NaN, infinity, binary floating point JSON amounts, excessive decimals and oversized values.
- SKU and optional barcode are unique. Optional blank barcode becomes NULL in the UI.
- Foreign keys, quantity/value checks and a partial unique open-session index reinforce service validation.

DB triggers block UPDATE/DELETE on posted sale, line, payment, movement, receipt, return, refund, cash-movement and audit tables. A database owner can still alter triggers; use a restricted runtime role and secure the Windows account. This is an audit trail, not tamper-proof cryptographic accounting.

## Android extension

The JSON API can later serve Android on the shop LAN after TLS, network exposure, mobile credential storage and device access are designed. Android is not required to run this version. Independently disconnected sales are a separate project: stock allocation, conflict policy, durable device queues and reconciliation must be defined before enabling them.

See [AMENDMENTS.md](AMENDMENTS.md) for the shared-stock allocation model and upgrade invariants.
