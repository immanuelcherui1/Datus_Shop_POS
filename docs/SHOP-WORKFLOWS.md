# Shop workflow refinements

## Selling packs and loose units
New sale starts in Wholesale / Pack. Select a product, switch the default selling mode to Wholesale / Unit, then select it again. The cart keeps two lines. Retail / Pack and Retail / Unit behave the same way. Repeated selections of the same product and mode increase that line's quantity; changing a line into an existing mode is disabled. Wholesale and retail still require separate transactions.

Both lines debit the same allocation. Checkout locks each product once and checks the combined quantity before posting. Cost is reserved sequentially so the final unit consumes any valuation rounding residue. A rejected checkout posts nothing. The API accepts distinct `(product_id, mode)` pairs and rejects duplicate pairs.

## Reorder thresholds
The product form accepts whole packaging units via `reorder_packs`. The server multiplies by `pack_size` and continues storing `reorder_level` in base units for reporting and compatibility. No database migration or reinterpretation of historical thresholds occurs. Existing fractional-pack thresholds appear blank in the edit field: leaving it blank preserves the original base threshold; entering a whole number replaces it.

## Authorized adjustment
Enter your own current password, allocation, product, quantity unit, signed quantity and reason. Selecting packs multiplies the quantity by the current pack size. The added-stock cost remains **per base unit**; negative adjustments consume the allocation's weighted cost. Password confirmation runs before idempotency replay, is rate limited, and is omitted from audit details and the retry digest. Passwords are never persisted in browser storage. Wrong passwords return 403 without ending the session.

API: `POST /inventory/adjustments` requires `password`; `unit` is `unit` (default) or `pack`. Audit details include entered quantity, chosen unit and converted base quantity.

## Purchase prices
Product selection suggests weighted stock cost per chosen unit. Switching between base unit and pack converts the entered cost, rounded to six decimal places, so an edited supplier cost is preserved. Line total is quantity times selected-unit cost; the order total sums its lines. Zero stock value produces a zero suggestion: enter the supplier's quoted cost. Receiving still posts actual goods and cost separately.

## Owner account management
Users → Edit changes username, role, active status and optionally password (12–200 characters). Leave the password blank to retain it. Remove access disables sign-in and revokes active tokens; it never deletes the user row or transaction history. Edit can reactivate an account. Your current owner account cannot be removed or demoted. Changing your own credentials requires signing in again.

API: owner-only `PUT /users/{id}` requires username, role and active; password is optional/null. Updates use idempotency keys, enforce branch scope and emit audit records without password contents. Owner changes lock the branch to serialize final-owner checks.
