# Inventory module

Read this before modifying `models.py`, `services.py`, receipt posting, checkout or returns.

## Authoritative history

`Movement.quantity` is positive for stock received and negative for stock consumed. `Movement.value` follows the same inventory-value direction. Current quantity/value must equal the sum for `(branch_id, product_id)`. `Stock` is only the cached aggregate; there is no endpoint for overwriting it.

Each sale movement links to `SaleLine`; goods receipts link to `Receipt`; restocked returns link to `ReturnLine`. Adjustments require a reason, authorized user and audit event. All movement rows include actor, branch, timestamp and product. Fix incorrect entries through a new authorized compensating adjustment that names the original movement in its reason. Dedicated reversal documents and reversal foreign keys are future work.

## Weighted-average costing

If 10 units worth 50 and 10 units worth 70 are on hand, average cost is 120 / 20 = 6. Selling 3 units posts quantity -3 and value -18. A subsequent receipt adds its actual cost; future sales use the new average. Selling the final units consumes the exact remaining value to avoid rounding residue.

Each sale line snapshots its total consumed cost. Product price edits cannot change historical gross profit. A restocked return adds back its original sale cost; a damaged return refunds money without returning sellable stock. The reporting module keeps damaged returned goods as a cost.

## Packs

Base quantity = sold quantity × conversion. Unit sales have conversion 1; pack sales in either channel use the snapshotted pack size. Wholesale price is the price of **one pack**, not a discounted base-unit price. Pack size and selected conversion are copied to the sale line. Multiplication that requires more than three base-unit decimals is rejected.

Purchase orders support packs or base units and convert to base quantities/costs on the server. Goods receipts and adjustments use base units; receiving two cartons of 12 means entering 24 received units. Receipts can record actual cost separately from the ordered cost.

## Reconciliation

```powershell
.\.venv\Scripts\python.exe -m flask --app backend/datus reconcile
```

The command compares cached quantity/value with grouped immutable movements, using one aggregate query per branch. Exit code is nonzero when a discrepancy exists. The Inventory screen exposes the same comparison. Never hide a discrepancy by editing the balance. Stop posting, back up, investigate the originating transactions, and repair via an independently reviewed migration or compensating transaction. Automated cache rebuild is intentionally not exposed to cashiers.

## Concurrency and tests

PostgreSQL `FOR UPDATE` serializes stock changes. The immutable ledger and cache commit together. Tests attempt two simultaneous checkouts against one remaining unit and assert exactly one physical sale, including the identical-key retry case. SQLite tests validate workflow behavior but do not prove PostgreSQL locking.

Not implemented: batch quantities/expiry tracking, serial numbers, reservations, warehouses, stock counts and negative-stock overrides. A manually maintained product expiry indicator and internal wholesale-to-retail allocation are implemented. Do not use this release for a business that requires these controls without adding and testing them first.

## Quantity entry and display

Wholesale sale/return quantities are whole packs. Pack sizes, reorder levels, purchase orders, receipts and manual stock adjustments accept whole base units. Retail sales/returns keep up to three decimal places for weighed or measured items. Prices remain decimal amounts; valuation retains its existing precision. Tax-rate precision is unchanged.

Quantity displays omit trailing zeros (`12.000` becomes `12`). Fractional stock produced by retail trading remains accurate (`29.500` becomes `29.5`); history is never rounded or rewritten. Legacy fractional wholesale sales/returns retain their return eligibility. Existing fractional purchase balances may require a reviewed correction before completing receipts under the new whole-unit rule.

The desktop sidebar scrolls vertically independently of the workspace on short screens or at increased zoom. The mobile horizontal navigation is unchanged.

## Wholesale and retail allocations

See [AMENDMENTS.md](AMENDMENTS.md) for allocation equations, migration policy, paired ledger entries, channel costing, historical returns and purchase workflows. Wholesale and retail are parts of one cached total; transfers never increase total business stock or value. Reconciliation checks total and retail balances; wholesale follows by subtraction.
