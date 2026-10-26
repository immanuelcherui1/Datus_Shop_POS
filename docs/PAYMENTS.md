# Checkout, payments and returns

## Current settlement support

`cash` records physical money retained in the drawer. `external_mobile`, `external_card` and `external_bank` record settlement that an owner or manager has independently verified outside DATUS. Every external record requires a reference, unique within its method. DATUS does not contact a provider, initiate a charge, read card data, or verify a mobile notification in this release.

The labels intentionally say **verified external**. Cashiers cannot post these methods. An external refund similarly requires an independently verified reference; recording it does not move money at the provider.

Payments must sum exactly to the server total. There is no credit or partial-payment sale. Cash should be entered net of change. Non-cash settlement is excluded from the physical drawer balance.

## Safe checkout retry

The client sends a cryptographically random `Idempotency-Key`. The server scopes it to user, operation and path and hashes the JSON payload. It saves the successful response in the same transaction as sale, payment, movements and audit. A retry returns the original result; a changed payload returns 409. Two simultaneous claims cannot both succeed.

The UI retains the key while an identical operation is retried. Do not refresh after an uncertain result: retry on the same screen, or inspect Sales history before posting again. Durable crash/reload recovery is not implemented. Suspended carts live in sessionStorage, contain no payment confirmation, and are requoted when resumed.

## Provider integration contract

`integrations.py` defines a provider verification interface and a fail-closed unconfigured provider. It is an extension boundary, not a working Daraja integration. Before enabling one, add and test:

1. Provider-specific request authentication and secret storage.
2. Payment attempts with pending/verified/failed/reversed states.
3. Callback signature or provider-supported authentication plus independent server verification where needed.
4. Unique provider event identifiers and transaction references.
5. Merchant account, currency and amount checks against the expected transaction.
6. A transactional outbox, durable retries and reconciliation of ambiguous outcomes.
7. An explicit stock reservation/finalization policy if payment arrives before inventory is committed.
8. Refund settlement states and provider reconciliation.

Never call a provider while holding stock locks and never mark payment successful from a browser flag. No placeholder callback endpoint accepts fake success in this release.

## Returns

Returns reference the original sale and line IDs. The service locks the sale and sums previous return quantities. The cumulative quantity cannot exceed the sold quantity. Refund allocations reference original payment IDs and cannot exceed the remaining paid allocation. Restock disposition posts inventory at the original cost; damaged disposition does not add stock.

Partial refunds use cumulative rounding: round the amount due for total returned quantity, then subtract amounts already refunded. This prevents repeated partial returns from exceeding the original rounded line amount. Returns are reported on their posting date rather than rewriting the original sales day.

## Register

One open session per branch is enforced by a database partial unique index. Expected cash = opening float + cash sales − cash refunds. Closing records expected, actual, variance and notes; a nonzero variance requires manager/owner adjustment permission and an explanation. Cash-in/out expense handling is not in the first release.
