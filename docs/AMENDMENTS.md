# Wholesale and retail amendments (0.3.0)

## Upgrade an existing shop

Close every trading session using the previous application version, make an encrypted backup, and keep its recovery key separately. Then close the controller and install the new version. Migration `0003` refuses to run while a session is open; this prevents mixing legacy cash-only reconciliation with the new M-Pesa ledger. If refused, reopen the previous version and close its session before trying again. The installed controller also takes an encrypted backup before applying a new migration.

Existing stock is assigned to **wholesale**, with zero allocated to retail. In Inventory ledger, allocate the physical retail shelf stock before making new retail sales. Do not add an opening adjustment for goods already in stock: that would duplicate stock.

Historical sales, payments, receipts, prices, quantities and movements are not rewritten. Old movements receive the label `legacy` and count toward wholesale reconciliation. Historical mixed sales remain readable. Legacy sale returns go to wholesale because their original allocation was not recorded. Historical session M-Pesa reconciliations and closing user are shown as unavailable, not invented. New records snapshot the operator and transaction channel.

Migration is forward-only; rolling back requires restoring the pre-upgrade backup into an empty database using the earlier application version. Do not run an older version against the upgraded database.

## One inventory, two allocations

`Stock.quantity` and `Stock.value` remain the business totals for a product and branch. `retail_quantity` and `retail_value` are the allocated portion; wholesale is the total minus that portion. Database constraints prevent negative or overallocated balances.

Every allocation locks the existing stock row, removes quantity/value from wholesale, adds exactly the same amounts to retail, and inserts two immutable `Movement` records with one `TR-…` reference. The transaction commits once. Retries with the same idempotency key cannot transfer twice. Total business quantity and value do not change.

Purchases enter wholesale only. Sales consume their own channel. Restocked returns from new sales return to their original channel at the recorded cost. Adjustments require an explicit channel, reason and existing adjustment permission. Cost is averaged within each allocation; transferring stock carries its current wholesale cost. The final unit consumes residual value to avoid rounding dust.

Reconciliation compares the total ledger against total cached balances, then the retail ledger against the retail cache. Wholesale is derived from those balances. Transfers are excluded from net business stock movement charts.

## Selling and prices

| Transaction | Selling unit | Price | Stock consumed |
| --- | --- | --- | --- |
| Wholesale | Pack | Wholesale pack price | Quantity × snapshotted pack size |
| Wholesale | Unit | Wholesale pack price ÷ pack size | Quantity base units |
| Retail | Unit | Retail unit price | Quantity base units |
| Retail | Pack | Retail unit price × pack size | Quantity × snapshotted pack size |

A sale cannot mix wholesale and retail channels. Complete, clear or suspend a cart to change channel. All pack and wholesale quantities are whole numbers; retail base-unit quantities retain three decimals. Unit prices are snapshotted to six decimals to support divided wholesale prices; line totals and settlement amounts are rounded half-up to two decimals. Browser previews are indicative; the server calculates the authoritative quote and checkout.

Cash, M-Pesa (`external_mobile`) and Other (existing card/bank records) can be split across a transaction. Their sum must equal the exact total. External references and existing role restrictions remain mandatory; DATUS does not initiate or verify provider payments. Receipt and sales history display the authenticated operator, channel, unit, original price, discounts, payment allocations and zero balance. User, channel, method and inclusive business-date filters are available.

## Purchasing and catalogue

Categories and units can be searched using the product form's suggestions or typed inline. Saving the product saves reusable options. Packaging unit and pack size define conversions; historical sale/purchase snapshots do not change when the catalogue changes.

Suppliers have phone, email, address and business details. Creation rejects an existing case-insensitive trimmed name; old duplicate records are not silently merged. The purchase page lists and edits suppliers.

Save a draft purchase order to review/edit it, or confirm it immediately. Only drafts can be edited. Confirmation still adds no stock. Product selection searches the catalogue and sorts zero/low quantities first. Selecting base units or packs proposes the corresponding current average cost, which the operator can change. The order snapshots description, selected unit, conversion, quantity and cost. Browser Print / Save PDF includes business name, supplier contact information, reference, preparer, totals and signature area.

Goods receiving accepts actual **base-unit** quantities and optional actual cost per base unit (six decimals); blank cost uses the order's base-unit cost. Partial delivery is supported; overdelivery and receiving an unconfirmed draft are rejected. The immutable receipt movements record actual quantity/cost independently of the order. There is no supplier payable accounting ledger.

## Sessions and reports

New sessions record Cash and M-Pesa opening balances separately. Each sale payment/refund creates a signed immutable session movement for the corresponding method. Expected closing = opening + receipts − refunds. Closing records actual balances, variances, authenticated closing user and **Remarks**; nonzero variances require existing manager/owner adjustment permission and an explanation. Other payments are reported but do not affect Cash or M-Pesa balances. Provider withdrawals, deposits and fees are not automatically imported; reconcile only the shop settlements recorded here.

Session history preserves both reconciliations. Dashboard date presets offer one day, seven days, thirty days, and custom ranges of up to 367 days. Charts show gross sales, best-selling base-unit quantities, channel/payment totals and net stock movements. Daily accounting reports continue to show refunds and net profit calculations separately.

Stock health is current, independent of the selected sales dates. Low-stock includes zero stock and opens an actionable list; select one or multiple products to seed a purchase draft. The top quarter of products with sales is labelled fast-moving; remaining sold products are slower-moving; no sales means non-moving. This is a relative ranking by base units before returns, not a demand forecast, and units differ between products.

Optional product expiry records the **earliest known on-hand expiry**, maintained by the operator. The dashboard shows expired/next-30-day products with stock. There is no lot/batch quantity tracking or automatic removal of the expiry date after selling a batch.

## Implementation and verification

- Schema: `backend/migrations/versions/0003_shop_amendments.py`.
- Posting and allocation: `backend/datus/services.py`; no intermediate service commits.
- Validation, APIs and reports: `schemas.py`, `api.py`; existing authentication, branch scoping and idempotency wrapper remain in use.
- Cross-module tests: `backend/tests/test_amendments.py`; migration preservation tests and PostgreSQL concurrency tests supplement the existing suite.
- Windows runtime grants only the additional supplier update / draft-line delete privileges needed by the new flows. Immutable transaction tables remain protected.

Run the full SQLite and PostgreSQL suites, frontend tests/build, and frozen Windows acceptance before deployment. Test a copy of the shop backup and hardware on the destination computer before resuming live trade.
