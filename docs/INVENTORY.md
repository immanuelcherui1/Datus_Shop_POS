# Inventory module

Read this before modifying `models.py`, `services.py`, receipt posting, checkout or returns.

## Authoritative history

`Movement.quantity` is positive for stock received and negative for stock consumed. `Movement.value` follows the same inventory-value direction. Current quantity/value must equal the sum for `(branch_id, product_id)`. `Stock` is only the cached aggregate; there is no endpoint for overwriting it.

Each sale movement links to `SaleLine`; goods receipts link to `Receipt`; restocked returns link to `ReturnLine`. Adjustments require a reason, authorized user and audit event. All movement rows include actor, branch, timestamp and product. Fix incorrect entries through a new authorized compensating adjustment that names the original movement in its reason. Dedicated reversal documents and reversal foreign keys are future work.

## Weighted-average costing

If 10 units worth 50 and 10 units worth 70 are on hand, average cost is 120 / 20 = 6. Selling 3 units posts quantity -3 and value -18. A subsequent receipt adds its actual cost; future sales use the new average. Selling the final units consumes the exact remaining value to avoid rounding residue.

Each sale line snapshots its total consumed cost. Product price edits cannot change historical gross profit. A restocked return adds back its original sale cost; a damaged return refunds money without returning sellable stock. The reporting module keeps damaged returned goods as a cost.

## Packs

Base quantity = sold quantity × conversion. Retail conversion is 1. Wholesale conversion is the product's pack size. Wholesale price is the price of **one pack**, not a discounted base-unit price. Pack size and selected conversion are copied to the sale line. Multiplication that requires more than three base-unit decimals is rejected.

Purchases and adjustments use base units and cost per base unit. Receiving two cartons of 12 requires entering 24 units. The UI explains this; there is no implicit purchase pack conversion.

## Reconciliation

```powershell
.\.venv\Scripts\python.exe -m flask --app backend/datus reconcile
```

The command compares cached quantity/value with grouped immutable movements, using one aggregate query per branch. Exit code is nonzero when a discrepancy exists. The Inventory screen exposes the same comparison. Never hide a discrepancy by editing the balance. Stop posting, back up, investigate the originating transactions, and repair via an independently reviewed migration or compensating transaction. Automated cache rebuild is intentionally not exposed to cashiers.

## Concurrency and tests

PostgreSQL `FOR UPDATE` serializes stock changes. The immutable ledger and cache commit together. Tests attempt two simultaneous checkouts against one remaining unit and assert exactly one physical sale, including the identical-key retry case. SQLite tests validate workflow behavior but do not prove PostgreSQL locking.

Not implemented: batches, expiry, serial numbers, reservations, warehouses, stock counts, transfers and negative-stock overrides. Do not use this release for a business that requires these controls without adding and testing them first.
