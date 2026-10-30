# DATUS — Retail & Wholesale POS

DATUS is a local-first point of sale and stock management application for a single Windows 11 computer. React provides the counter interface, Flask owns business rules, and PostgreSQL stores the authoritative records. Cash trading continues when the internet is unavailable; cloud backup is a separate, optional process.

**Current verified installer: 0.3.2 (branding and shop workflows) · Windows 11 x64. Release status: initial implementation, not an audited or certified production release.** Read [known limitations](docs/STATUS.md) and complete the acceptance checklist before using real shop data. Live M-Pesa/card integrations and an Android APK are not included. No default passwords, credentials, or real customer data are shipped.

## Stock allocation upgrade (0.3.0)

Wholesale and retail are **two allocations of one inventory**, not duplicate inventories. Purchases enter wholesale; authorized transfers allocate quantity and cost to retail without changing business totals. The update adds four selling-unit choices, Cash/M-Pesa reconciliation, supplier editing, draft purchase review and printing, reusable categories/units, receipt accountability, and interactive inventory insights.

**Before upgrading an existing shop:** close its trading sessions in the previous version, create a backup and keep the recovery key, then close the controller. Existing stock is assigned to wholesale; allocate the goods already on retail shelves before retail checkout. Never re-add those goods as opening stock. See [amendment workflows, migration policy and limitations](docs/AMENDMENTS.md). The verified 0.3.2 download below includes these amendments.

## Logo and appearance (0.3.1)

The supplied DATUS logo and icon now appear on sign-in, navigation, documents, browser tabs and Windows application/installer icons. Use **Dark mode / Light mode** on sign-in or in the workspace header. Your choice is saved in this browser; the first visit follows the device theme. Receipts and purchase orders retain white paper styling. See [branding and theme maintenance](docs/BRANDING.md). The verified 0.3.2 installer below includes this update.

## Shop workflow refinements (0.3.2)

- New sales default to Wholesale / Pack. Add the same item in pack and unit modes to create separate lines in either channel (for example, 7,500 + 150 = 7,650 before any configured tax).
- Product reorder thresholds are entered in whole packaging units. Existing thresholds remain unchanged until edited.
- Stock adjustments require the signed-in user's password and accept positive/negative base units or packs. Added-stock cost is always per base unit.
- Purchase orders derive costs from the current stock valuation, convert the cost when switching units, and show line and order totals. Enter the supplier's actual cost when needed, especially if there is no stock history/value.
- Owners can edit usernames, passwords and roles or remove access. Historical records are retained, and existing sessions are revoked.

See [shop workflow details and API notes](docs/SHOP-WORKFLOWS.md). The verified 0.3.2 installer below includes all of these changes.

## What is implemented

- Password authentication, HttpOnly JWT cookies, CSRF protection, login throttling, and backend role enforcement.
- Owner, manager, cashier, inventory, and accountant roles; records are scoped to the signed-in user's branch.
- Product search by name, SKU or barcode; unique SKU/barcode; product edits with audit snapshots.
- Wholesale/pack, wholesale/unit, retail/unit and retail/pack prices, with server-calculated conversions and separate transaction channels.
- Immutable stock movements, atomically updated quantity/value caches, and reconciliation.
- Editable suppliers, draft/confirmed purchase orders with pack/base-unit costs, printable orders, partial actual goods receipts, and weighted-average costing per allocation.
- Server-calculated quotes, authorized line discounts, exclusive tax, atomic checkout, and idempotent retries.
- Cash and split settlement; privileged recording of **already independently verified** external payments.
- Sales history, immutable receipt snapshots, browser printing / Save as PDF, suspended carts for the current browser session.
- Controlled partial returns, cash/manual external refund allocations, and restock versus damaged disposition.
- Cash and M-Pesa opening/closing reconciliation, operator accountability, Remarks and session history; manager/owner authorization for explained variances.
- Daily sales/refunds/profit reports, date-range charts, inventory health, actionable low-stock purchasing, payment/channel breakdowns and daily CSV export.
- Owner-controlled user creation, credential/role updates and access removal with session revocation; administrator password recovery and audit viewer.
- Database migrations, SQLite functional tests, PostgreSQL concurrency tests, frontend tests, and GitHub Actions.
- Streaming encrypted PostgreSQL backup, restore to an empty database, and retryable S3-compatible upload.
- Self-contained Windows installer, graphical owner setup, and a desktop controller.
- Optional Tailscale Funnel access through a separate secured listener; local trading stays available offline.
- Independently scrolling desktop navigation and horizontal mobile navigation.

## Architecture and source map

```text
DATUS/
  backend/
    datus/
      __init__.py       Application factory, configuration, error handling, static serving
      extensions.py     Database, migrations, JWT and limiter initialization
      models.py         Tables, constraints and immutable-history ORM guards
      schemas.py        Strict request validation and exact decimal inputs
      security.py       Roles, permissions and record scope
      remote.py         Exact remote host/origin checks and HTTPS cookie requirements
      services.py       Inventory, checkout, receiving and return transactions
      api.py            HTTP routes, idempotency, serialization and daily reporting
      cli.py            Owner bootstrap, recovery, demo catalogue, reconciliation
      integrations.py   Fail-closed boundary for future payment providers
    migrations/        Versioned schema and database immutability triggers
    tests/             Functional, integrity, security, backup and concurrency tests
    run.py             Waitress entry point for Windows
  frontend/
    src/pages/         Separate screens for each operational module
    src/components/    Shared form, status and pagination components
    src/api.js         Cookie/CSRF transport and retry-key handling
    src/main.jsx       Application shell and permission-aware navigation
  desktop/             First-run wizard, local/private PostgreSQL lifecycle, remote listener
  packaging/           Reproducible Windows installer build and bundled runtimes
  scripts/             Windows setup/startup, Funnel configuration and encrypted backup tooling
  docs/                Architecture, module guides, API, security and release limits
```

See [amendment module guide](docs/AMENDMENTS.md), [architecture and schema](docs/ARCHITECTURE.md), [inventory](docs/INVENTORY.md), [checkout and payments](docs/PAYMENTS.md), [API reference](docs/API.md), [Windows operations](docs/WINDOWS.md), and [backup / restore](docs/BACKUP.md).

## Windows installer (recommended for the shop computer)

[Download DATUS 0.3.2 for Windows x64](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41061361459/artifacts/12981110065). GitHub sign-in may be required. This verified artifact contains the installer, SHA-256 checksum, build information and acceptance-test result. It is retained until January 28, 2027; check later successful **Windows installer** workflow runs for newer builds.

1. Download and extract the ZIP on the shop computer.
2. If upgrading, close all trading sessions in the previous version, back up, and close the controller. Then run `DATUS-Setup-0.3.2-x64.exe` under the Windows account that operates the shop.
3. Choose desktop and optional sign-in shortcuts. Python, the interface and private PostgreSQL are bundled; no developer tools are required.
4. Open **DATUS**. On first launch, enter your shop name, owner username and a password of at least 12 characters. There are no default credentials. Upgrades keep the existing shop.
5. Keep the controller open while trading. **Open DATUS** opens the browser at the correct local address; the installer chooses its own port, so do not assume it is 8080.
6. Follow [First trading session](#first-trading-session) below.

Current installers are **unsigned**. Verify the source and compare `Get-FileHash .\DATUS-Setup-0.3.2-x64.exe -Algorithm SHA256` with the supplied `.sha256` file. The installer passed installation, first-run setup, checkout, encrypted backup, restart, separate remote-listener and data-preserving uninstall checks. Live hardware and public Funnel access still require verification on the shop computer.

| Location | Purpose |
| --- | --- |
| `%LOCALAPPDATA%\Programs\DATUS` | Installed application and bundled runtimes |
| `%LOCALAPPDATA%\DATUS` | Business database, configuration and logs |
| `%LOCALAPPDATA%\DATUS\backups` | Encrypted backup files |
| `%LOCALAPPDATA%\DATUS\backup.key` | Recovery key needed to decrypt backups |

Uninstalling removes application files and shortcuts, **not business data or backups**. Reinstall under the same Windows account to reuse the shop. See [installer instructions](docs/INSTALLER.md) for upgrades, checksums and build details.

## Remote access with Tailscale Funnel

Funnel setup runs on the **shop computer**, using DATUS 0.2.2 or newer. It publishes a public HTTPS login page; visitors do not need Tailscale but must sign in to DATUS. Public access is disabled until you explicitly enable it. For private device-only access, consider Tailscale Serve instead; the commands here configure Funnel.

1. Install DATUS, initialize the owner account if needed, and install [Tailscale for Windows](https://tailscale.com/download/windows). Sign in to your own tailnet on the shop computer.
2. Close the DATUS controller. In PowerShell, under the same Windows account, run:

```powershell
$setup = "$env:LOCALAPPDATA\Programs\DATUS\_internal\setup\funnel.ps1"
& $setup -Action Prepare
```

3. Reopen DATUS and wait for the local workspace to be ready. In the same PowerShell window, run:

```powershell
& $setup -Action Enable
```

4. Complete any Tailscale HTTPS/Funnel approval requested. If the command exits before enabling, finish the approval and rerun it. Use the printed `https://...ts.net` address from a phone on mobile data to test login, reports, receipts and logout.

To inspect or turn off public access:

```powershell
& $setup -Action Status
& $setup -Action Disable
```

The script checks the dedicated remote listener before forwarding it and refuses to silently replace existing Serve/Funnel services. The remote connection uses secure cookies, CSRF and exact host/origin checks. The database and backup folders are not exposed. Your separately hosted domain is not automatically connected to this Tailscale address.

Leave the shop PC awake, online and DATUS running for remote access. Local trading keeps its original loopback connection and works offline. Funnel configuration persists across restarts until disabled; closing DATUS stops application access but does not remove the Funnel configuration. See [remote-access setup, security limits and troubleshooting](docs/REMOTE_ACCESS.md). No live Funnel endpoint was enabled during development.

## Backups: what is available now

In the installed DATUS controller, click **Create encrypted backup**. The file is saved under `%LOCALAPPDATA%\DATUS\backups`. Preserve a separate recovery copy of `backup.key`; encrypted backups cannot be restored without it.

**Automatic hourly/daily scheduling is not built into the installer yet.** The desktop button creates a manual local backup. The source-code backup tool supports Windows Task Scheduler and retryable S3-compatible uploads when configured, but the installer button does not automatically upload files. Cloud accounts, storage and credentials are not provisioned by DATUS. SFTP/cPanel uploads are not implemented.

Keep a copy of completed encrypted backups off the shop computer, with the recovery key stored separately. Do not put backups in a public website folder. A backup is a snapshot, not live synchronization or remote hosting. Practice restoration into an empty database before relying on it. See [backup configuration, scheduling and restore drills](docs/BACKUP.md).

## Manual Windows 11 installation

This is the developer/source alternative. Skip these commands when using the installer.

Use a local, non-synchronized folder, for example `C:\DATUS`. Do not place the PostgreSQL data directory in OneDrive or a network share.

Prerequisites:

1. Python 3.12 with the `py` launcher.
2. Node.js 22.12 or newer (Node 24 also works).
3. PostgreSQL 17, running as its Windows service. Include its `bin` directory in PATH for `psql`, `pg_dump` and `pg_restore`.
4. Git, if cloning directly from GitHub.

From PowerShell:

```powershell
git clone https://github.com/immanuelcherui1/Datus_Shop_POS.git C:\DATUS
Set-Location C:\DATUS
.\scripts\setup.ps1
```

If your PowerShell execution policy blocks local scripts, review the scripts, then use an organization-approved policy or execute the equivalent commands below. Do not disable machine-wide security settings just to install DATUS.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe scripts\configure.py
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

The configuration helper creates `.env` with random authentication secrets. It never prints them and refuses to overwrite an existing file. Edit `DATABASE_URL` with the correct database credentials. URL-encode special characters in the password. Keep `.env` out of Git and restrict access to the Windows account running DATUS.

For a straightforward local installation, create the database using PostgreSQL's administrator account:

```powershell
psql -U postgres -h 127.0.0.1
```

At the SQL prompt:

```sql
CREATE ROLE datus LOGIN;
\password datus
CREATE DATABASE datus OWNER datus;
\q
```

Use a unique generated password; there is no supplied production password. For stronger separation between runtime and migration privileges, follow [security](docs/SECURITY.md).

Apply the committed migrations and create the first owner:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend/datus db upgrade
.\.venv\Scripts\python.exe -m flask --app backend/datus create-owner
```

The owner password is prompted twice and must have at least 12 characters. `create-owner` refuses to run after an account already exists. Add subsequent users from **Users**.

Optionally add a development catalogue before adding your own products:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend/datus seed-demo
```

Demo products start with zero stock and example tax settings. They never insert fake sales or payments. Do not seed a live shop catalogue.

Start the application:

```powershell
.\scripts\start.ps1
```

Open **http://127.0.0.1:8080** in the browser. DATUS binds to loopback by default; it is not exposed to the internet or shop Wi-Fi. The built frontend and API share one origin. Close the terminal to stop a foreground server. Optional sign-in startup is documented in [Windows operations](docs/WINDOWS.md).

## First trading session

1. Sign in as the owner and create staff accounts.
2. Add products. Enter retail price per base unit, wholesale price per pack, and pack size. Confirm tax rates and units before trading.
3. Add a supplier and purchase order. Choose base units or packs and the corresponding unit cost. Save a draft to review, then confirm it. Print / Save PDF does not add stock.
4. When goods arrive, post actual delivered **base-unit** quantities and costs. Goods enter wholesale. In **Inventory ledger**, allocate stock to retail for shelf sales; transfers leave business totals unchanged.
5. Open **Cash register** and enter Cash and M-Pesa opening balances separately.
6. Open **New sale**, choose Retail or Wholesale and Unit or Pack, then search or scan products. Barcode scanners must act as a keyboard and send Enter.
7. Check the server-calculated total. Enter payments equal to the amount due. For cash, record the amount retained **after giving change**.
8. Complete the sale and print its receipt or save it as PDF. Use **Sales history** to reprint it later.
9. Review **Daily reports**, reconcile the inventory ledger, and close the register with actual Cash/M-Pesa balances and Remarks.
10. Run the encrypted backup and confirm off-device upload when configured.

Example: a carton contains 12 units. Retail is KES 10 per unit, wholesale is KES 110 per carton. Selling two cartons reduces stock by 24 units and charges KES 220 before configured tax. Prices and pack conversion are copied into sale lines, so editing the product later does not alter the receipt.

## Quantity rules

- Prices and payment amounts retain decimal precision; retail quantities support up to three decimal places.
- Wholesale quantities and packs in either channel are whole numbers. Pack sizes are whole numbers and reorder thresholds are entered in whole packs. Purchase orders and adjustments support whole packs or base units; goods receiving uses whole base units.
- Quantity displays remove padding (`12.000` becomes `12`) without rounding genuine fractional retail stock (`29.500` becomes `29.5`).
- Historical records are not rewritten. Legacy fractional wholesale returns and purchase balances have special considerations described in [inventory rules](docs/INVENTORY.md).

## Development and verification

For UI development, run the Flask/Waitress server on port 8080, then:

```powershell
npm.cmd --prefix frontend run dev
```

Use the Vite URL it prints. Its `/api` proxy keeps requests same-origin. Production serves the compiled frontend directly from Flask.

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

By default, backend tests migrate an isolated temporary SQLite database. Two concurrency cases are deliberately skipped. To run the complete suite, create a **disposable PostgreSQL database named `datus_test`**, then:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://YOUR_TEST_USER:YOUR_TEST_PASSWORD@127.0.0.1:5432/datus_test'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

**The PostgreSQL fixture drops and recreates the `public` schema before every test. Never point it at live data.** It requires a test database name containing `test` and never takes the production `DATABASE_URL` implicitly. Run sequentially; the fixture is not designed for pytest-xdist.

GitHub Actions runs both database suites against PostgreSQL 17, plus frontend tests and production build. Test results and remaining acceptance work are tracked in [STATUS.md](docs/STATUS.md).

## Data integrity promises and boundaries

- Stock movements are the history; stock balances are a cache. Both change in the same database transaction.
- PostgreSQL row locks prevent concurrent checkout from silently consuming the same stock.
- All financial arithmetic uses Python `Decimal` and database `NUMERIC`. APIs accept monetary and quantity values as strings.
- A completed sale contains immutable descriptions, prices, discounts, tax, conversion and cost snapshots.
- Retrying the same operation key cannot post the same transaction twice. A changed payload cannot reuse a key.
- External provider actions are not part of a database transaction. This release does not pretend that recording a reference performs a payment.
- An uncertain checkout is saved in browser sessionStorage with its original request and retry key. After navigation or refresh, New sale shows a recovery screen and blocks a different checkout until resolved. Closing the browser session or clearing browser storage can lose this recovery record: inspect Sales history before creating another sale.

## Before live use

Complete [the security and operational checklist](docs/SECURITY.md). In particular, verify your tax setup, physical receipt printer, opening stock and valuation, real PostgreSQL test suite, backup recovery, staff permissions, and a full day-end cash reconciliation. Use a UPS and keep recovery material off this computer.

Android, multi-device offline synchronization, live Daraja callbacks, fiscal/e-invoicing integration, credit accounts, and full accounting are future modules. The current application is single-business and single-shop by design; it is not a multi-tenant SaaS system.

## 0.3.0 verification

Verified code: [`239496e`](https://github.com/immanuelcherui1/Datus_Shop_POS/commit/239496e2317701fbdef98df2d926307779b8f80c). [Integrity CI](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41023040299) passed: 40 SQLite tests (3 PostgreSQL-only cases skipped), 43 tests with PostgreSQL configured, 7 frontend tests and the production build. [Windows installer acceptance](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41023040277) passed, including stock allocations, M-Pesa reconciliation, supplier edits and draft confirmation under restricted runtime permissions. Legacy data migration preservation/refusal tests use disposable SQLite databases; PostgreSQL schema creation and competing stock allocations are covered by CI. Desktop/mobile browser checks used a separate demonstration database.

## 0.3.2 verification

Verified code: [`2bcf0fc`](https://github.com/immanuelcherui1/Datus_Shop_POS/commit/2bcf0fc3b8dc7e1beef2fec6842cff0522258396). [Integrity CI](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41061361562) passed 44 SQLite tests (3 PostgreSQL-only tests skipped), 47 PostgreSQL tests, 12 frontend tests and the production build. [Windows acceptance](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41061361459) passed installation, bundled branding resources, setup, trading, encrypted backup, restart and data-preserving uninstall. Browser checks verified wholesale default, two pack/unit lines with the correct combined total, and both themes using a disposable demo shop. New regressions cover combined-stock overselling, adjustment reauthentication/retries, pack conversion, owner credential changes and purchase-cost conversion.
