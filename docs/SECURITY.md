# Security and release acceptance

## Implemented controls

- Werkzeug scrypt password hashes, no default credentials, 12-character account-creation minimum.
- Eight-hour access tokens in HttpOnly cookies, SameSite Strict, CSRF double-submit checks for authenticated mutations.
- Logout and local password recovery invalidate all tokens for the affected user via a database token version.
- Login limit of 10 requests/minute/IP. In-memory limiter is appropriate to this one-process installation; it resets on restart.
- No permissive CORS; frontend/API share an origin. Same-origin JSON login prevents cross-origin form login requests.
- Server-side roles and branch scoping; cashier access restricted to their own sales.
- Marshmallow rejects unexpected fields, imprecise values and excessive input sizes.
- SQLAlchemy parameterization; database constraints and immutable-history triggers.
- Safe HTTP errors without SQL parameters, passwords, tokens or request-body logging.
- CSP, frame denial, MIME sniffing prevention and no-store API responses.

`COOKIE_SECURE=false` supports plain HTTP only on the loopback single-PC installation. For any remote access, terminate HTTPS and set it to true. Never expose plain HTTP authentication on Wi-Fi or the internet.

## Roles

| Capability | Owner | Manager | Cashier | Inventory | Accountant |
|---|---|---|---|---|---|
| Checkout / own sales | Yes | Yes | Yes | No | Read reports/sales |
| Product management | Yes | Yes | No | Yes | No |
| Purchasing / adjustments | Yes | Yes | No | Yes | No |
| Discounts / returns | Yes | Yes | No | No | No |
| Record verified external settlement | Yes | Yes | No | No | No |
| Register | Yes | Yes | Yes | No | No |
| Reports / audit | Yes | Yes | No | No | Yes |
| Create users | Yes | No | No | No | No |

Role permissions are enforced in backend decorators and service-level checks, not only by navigation visibility.

## PostgreSQL privilege separation

The simple installation role owns its database to make local setup practical. For deployment, use a separate migration owner and a restricted `datus_app` runtime role. Run migrations as the owner, then grant only CONNECT, schema USAGE, needed table SELECT/INSERT, sequence USAGE, and UPDATE on mutable state tables. Do not grant DELETE, schema CREATE, trigger management or table ownership to the runtime role.

Mutable tables needing UPDATE: `product`, `stock`, `user`, `purchase`, `purchase_line`, `cash_session`, `idempotency`. Posted tables need SELECT/INSERT only. `branch` and `supplier` currently only require SELECT/INSERT. Adjust grants when migrations add tables; test privileges against the complete posting suite. Backups and restores use separately controlled identities. Never give an internet-facing process a PostgreSQL superuser.

## Before real trading

- [ ] Confirm installed version, pinned dependencies, PostgreSQL migrations and integrity test results.
- [ ] Replace every placeholder configuration value and secure `.env` and key-file ACLs.
- [ ] Verify business name, currency, local date boundary, unit conversion and tax treatment with the shop's responsible accountant.
- [ ] Validate opening stock counts and cost valuation.
- [ ] Run a purchase, partial receipt, retail sale, wholesale sale, split settlement, return and day-end close using test data.
- [ ] Check stock and cash reconciliation; inspect audit records and immutable historical receipts.
- [ ] Test actual receipt printer, scanner and restart after simulated application failure.
- [ ] Create an encrypted off-device backup and successfully restore it to a separate database.
- [ ] Configure backup scheduling, cloud retention, disk monitoring and failure review.
- [ ] Restrict Windows accounts, enable device encryption and updates, and use a UPS.
- [ ] Train staff: an unverified mobile notification is not a successful payment.

No fiscal certification, tax-compliance certification, external penetration test or accounting audit is claimed. e-invoicing/fiscal integrations must be implemented if required for the shop's operation. Review dependencies periodically; pinned versions make builds reproducible, not automatically secure forever.
