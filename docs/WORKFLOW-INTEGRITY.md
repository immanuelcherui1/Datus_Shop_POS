# Stock, purchasing and money workflow rules (0.4.0)

## Quantities and costs
A product's base unit and pack size become fixed when its first stock movement or purchase order exists. Names, prices, category, packaging label and reorder threshold remain editable. Create a new SKU when the physical unit/package changes. This prevents existing quantities from being relabelled without conversion.

Purchase order line totals use the original entered quantity and selected-unit price, rounded per line to cents. Rounded base-unit display costs are never used to reconstruct the order amount. Default receipt valuation allocates the original exact price cumulatively to six decimals, including the final rounding residue. Actual receipt costs override the order estimate. The purchase screen preserves the original cost basis across repeated unit switches.

Goods receiving accepts base units or packs using the order's saved pack size. Actual cost, when entered, is per selected receiving unit. Legacy orders without a pack-size snapshot must use base units. No goods receipt is posted until a positive delivered quantity is entered; overdelivery is rejected atomically.

Suggested replenishment cost is the current inventory average while stock exists, otherwise the latest recorded positive purchase receipt/opening adjustment cost. A genuine zero-cost receipt remains zero; without recorded cost history, enter the supplier quote. Suggested price is not a supplier invoice.

## Stock allocation
Inventory ledger now transfers Wholesale → Retail or Retail → Wholesale. Select source, base units/packs, quantity and reason. Both movements share a reference and one transaction. Business quantity/value never changes. Whole pack quantities are required. Negative stock is rejected, including concurrent checkout/transfer attempts.

## Supplier payments
Receive goods first, then choose Record payment on the purchase. Only owners/managers can record payments. The payable is the value of goods actually received, rounded to cents, less recorded payments. Partial payments are allowed; payment above outstanding value is rejected. No advance-payment or supplier-credit-note workflow is implemented.

Record actual payments already made: Cash reduces the current till balance; M-Pesa reduces the tracked M-Pesa balance and requires a verified reference. Bank payments require a reference and appear in payment history but do not affect Cash/M-Pesa balances. All require an open trading session. DATUS does not initiate or independently verify external transfers.

## Other money movements and corrections
Cash register → Record money in/out handles actual top-ups, withdrawals and expenses. These affect register balances, not sales or gross profit. Supplier payments must use the purchase workflow so the payable is updated. Insufficient recorded funds block outgoing money and refunds; record actual funding first.

Money movement history shows signed amounts, source, session, purchase reference and reversal links. Reverse an erroneous manual entry/supplier payment only after the corresponding money has actually been returned. Reversal posts the opposite amount in the current session and reopens the supplier balance where appropriate. A movement can be reversed once; sale settlements use the sales return workflow. Posted rows are never edited or deleted.

Funds submissions retain an uncertain request in session storage. After a lost connection or reload, use Recover funds entry with the original retry key; do not pay again. Passwords are not stored in these requests.

## Upgrade handling
Migration 0004 preserves existing stock and immutable ledger rows/triggers. Existing purchases are marked payment status unknown: they cannot be paid through this screen because DATUS cannot know whether historical supplier bills were already settled. New orders enable payment tracking. Historical totals and original postings are not rewritten. Back up and close DATUS before installing.

## API
- Product PUT rejects base-unit/pack-size changes after movement/order history. GET /products includes unit_locked and supports up to 100 comma-separated ids.
- POST /inventory/transfers accepts source=wholesale|retail (default wholesale).
- POST /purchases/{id}/receipts accepts line unit=unit|pack; optional unit_cost is per selected receiving unit.
- Purchase responses include authoritative line_total/total, received_value, paid, outstanding, payments_tracked and payment history.
- POST /purchases/{id}/payments: amount, method, reason, optional external reference.
- GET /register/movements: paginated history; optional session_id.
- POST /register/movements: kind=cash_in|cash_out, method=cash|external_mobile, amount, reason, reference.
- POST /register/movements/{id}/reversal: reason and verified external reversal reference where applicable.
- All writes require idempotency keys. Money writes require cash_manage (owner/manager), branch scope and an open session. Lock order is register → purchase; inventory posting uses stock → product. Read/write sessions use the same register lock to serialize outgoing funds and closing.

## Regression coverage
The suite covers exact order totals; mixed receiving units; partial receipts and rounding residue; actual-cost overrides; cost after sell-out; blocked historical unit edits; draft conversion snapshots; reverse allocation and ledger reconciliation; duplicate/retried payments; overpayment and insufficient funds; reversal eligibility; Cash/M-Pesa/bank effects; cross-branch and role denial; immutable money history; upgrade preservation; refunds funded in the current session; concurrent outgoing payments and reversals on PostgreSQL; browser form recovery and unit toggling.

Automated tests cover these specified invariants, not every possible hardware/browser/environment interaction. Receipt printers, scanners, real provider settlements, cloud credentials and public remote access still need acceptance checks on the shop computer. This is not a full accounting ledger: taxes/fees on supplier invoices, credit notes, advances, expense profit reporting and historic payable reconciliation remain outside this workflow.
