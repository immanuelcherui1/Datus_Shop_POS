# Named packaging, line amounts and thermal receipts (0.5.0)

## Registering candles

Create one **Candles** product. Set base unit to **piece**, primary packaging
unit to **carton**, and pack size to **96**. Select **Configure multiple packaging
units**, then add **packet** with conversion **8**.

| Unit | Base pieces | Wholesale price | Retail price |
|---|---:|---:|---:|
| piece | 1 | blank (not sold) | 10.00 |
| carton | 96 | 768.00 | blank (not sold) |
| packet | 8 | 64.00 | 80.00 |

A blank channel price disables that selling choice; it is not zero. Zero is an
explicit free price, subject to the existing positive-sale-total rule. Conversion
is always directly to base units, so 12 packets × 8 pieces = 96 pieces per carton.
Purchase cost is independent of selling price. The reorder threshold uses the
primary packaging unit: 2 cartons = 192 pieces. Additional units do not create
additional stock balances. Up to 20 named units are supported.

After stock or orders exist, existing packaging names and factors cannot change
or disappear. Prices can change and new options can be added. Leave both prices
blank to stop selling an option; it remains available for stock and purchasing.
Base-unit changes require a new SKU. Do not relabel historical kilograms as grams.

## Using packaging throughout the shop

- Choose the package beside a catalogue card before adding it. The same product
  and package accumulate in one cart row; different packages have separate rows.
- Each cart row shows quantity × unit price and its server-calculated amount
  **after line discount and including line tax**. A separate note identifies tax.
  The bottom subtotal is after discounts and before tax; total includes tax.
- Wholesale and retail still require separate sales. Disabled channel prices are
  not selectable. Server validation also rejects unavailable choices and combines
  all rows of a product when checking stock, preventing carton/packet overselling.
- Receiving 10 cartons adds 960 pieces. Selling 2 wholesale cartons and 3 packets
  charges 1,728 and deducts 216 pieces. A retail packet plus 3 pieces charges 110
  and deducts 11 pieces from retail allocation.
- Purchase orders allow any defined package. Changing the selected unit derives
  cost directly from the original price and conversion, avoiding repeated rounding.
  One purchase line per product remains the rule; receive that line in any saved
  packaging unit or base units. The order snapshots all conversion options.
- Allocation transfers and password-authorized adjustments use the same units.
  Adjustment cost remains **cost per base unit**; its label explicitly says so.
  Returns use the original sale's saved conversion, price and valuation.

## XP-80S / Windows direct printing

Install the printer on the Windows **shop server**, using the vendor driver first.
If that driver does not accept RAW data, add a separate **Generic / Text Only**
Windows queue on the same physical port. Keep the normal driver for browser/PDF
printing. DATUS does not install drivers or change Windows printer settings.

1. Open a saved sale receipt and choose **Thermal printer / text receipt**.
2. Select the XP-80S's actual Windows queue (not Microsoft Print to PDF).
3. Select **Plain text only** to test text, or **ESC/POS built-in font** for commands.
4. Start with 48 columns for 80 mm paper; try 42 or 32 if your printer clips lines.
5. Choose **Print test**. Verify legibility, wrapping and paper feed. Enable cutting
   only after confirming your particular printer supports the ESC/POS cut command.
6. Choose **Print receipt copy**. This prints saved sale facts; it never posts a sale.

The exact XP-80S firmware/command support and physical quality must be checked on
the shop hardware. The implementation is generic Windows RAW plus ESC/POS, not
a claim of hardware certification. Plain text emits no control commands except
line endings. ESC/POS initializes normal Font A, size and alignment; cut is opt-in.
Text-only receipts use ASCII with replacement for unsupported characters and
omit the graphic logo. Names/references cannot inject printer control codes.
Browser/PDF printing remains available for branded receipts and reports.

Settings are remembered in the current browser. Remote access still prints on
the shop server, not on the phone or remote computer. Install and select the queue
under the Windows account running DATUS. Selling permission and branch access
are required; only installed queues can be addressed.

**Queued does not mean physically printed.** Check paper and Windows queue before
requesting another copy. A retry key is durably claimed before talking to the
spooler. Interrupted requests recover their original status without resending.
A crash after claiming but before sending can leave an uncertain job that never
printed; a crash after sending can leave an uncertain job that did print. Only an
explicit new copy should be sent after checking. There is no automatic print on
checkout and no automatic retry to the printer. A failed print never reverses or
repeats a sale, stock deduction or payment.

## API and maintenance

`Product.packages` is nullable JSON. Null keeps the legacy four selling choices;
an explicit array defines `key`, `name`, integer `conversion`, nullable
`wholesale_price` and nullable `retail_price`. Stable keys `unit` and `pack` identify
the base and primary packaging options. GET products adds `packaging_options` for
uniform discovery. Existing product price fields mirror the explicit base retail
and primary wholesale prices (0 when unavailable); consult the options for channel
availability. Explicit package prices are authoritative.

Cart, purchase, adjustment and transfer lines accept `packaging_key`. Legacy fields
remain supported. Non-base wholesale options use mode `wholesale`, non-base retail
options use `retail_pack`; base options use `wholesale_unit` / `retail`. Receiving
accepts a `packaging_key` from `PurchaseLine.packaging_snapshot`. Sale lines store
the key plus the immutable unit, conversion and price snapshot.

- `GET /api/printing/printers`: installed Windows queue names.
- `POST /api/printing/test`: a nonfinancial test slip.
- `POST /api/sales/{id}/print`: a saved receipt copy, scoped to the user's branch.
- Print body: `printer`, `columns` (32/42/48), `mode` (`text`/`escpos`), `cut`.
  POST requires `Idempotency-Key`; responses are `queued` (with job ID) or `unknown`.
  Print claims use the existing idempotency table and append audit events.

Migration 0005 adds nullable columns without rewriting legacy receipts, product
balances or immutable triggers. Back up and close DATUS before installing. Restore
a pre-upgrade backup instead of attempting a destructive schema downgrade.

Tests cover the candle example, disabled/mismatched options, combined overselling,
conversion locking, receipt/return snapshots, cost conversion, migration preservation,
line totals, print control sanitization, queued/uncertain retry recovery, branch
access and PostgreSQL concurrent print claims. Windows installer smoke uses a
simulated spooler; it does not prove physical printer quality.

Implementation references: [Microsoft RAW printing](https://learn.microsoft.com/en-us/windows/win32/printdocs/sending-data-directly-to-a-printer),
[printer enumeration](https://learn.microsoft.com/en-us/windows/win32/printdocs/enumprinters),
[WritePrinter constraints](https://learn.microsoft.com/en-us/windows/win32/printdocs/writeprinter),
[Generic/Text Only queue setup](https://qz.io/docs/setting-up-a-raw-printer-in-windows).
