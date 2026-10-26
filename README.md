# DATUS — Retail & Wholesale POS

DATUS is a local-first point of sale and stock management application for a single Windows 11 computer. React provides the counter interface, Flask owns business rules, and PostgreSQL stores the authoritative records. Cash trading continues when the internet is unavailable; cloud backup is a separate, optional process.

**Release status: initial implementation, not an audited or certified production release.** Read [known limitations](docs/STATUS.md) and complete the acceptance checklist before using real shop data. Live M-Pesa/card integrations and an Android APK are not included. No default passwords, credentials, or real customer data are shipped.

## What is implemented

- Password authentication, HttpOnly JWT cookies, CSRF protection, login throttling, and backend role enforcement.
- Owner, manager, cashier, inventory, and accountant roles; records are scoped to the signed-in user's branch.
- Product search by name, SKU or barcode; unique SKU/barcode; product edits with audit snapshots.
- Retail price per base unit and wholesale price per pack, with explicit pack-to-base conversion.
- Immutable stock movements, atomically updated quantity/value caches, and reconciliation.
- Suppliers, purchase orders, partial goods receipts, and moving weighted-average costing.
- Server-calculated quotes, authorized line discounts, exclusive tax, atomic checkout, and idempotent retries.
- Cash and split settlement; privileged recording of **already independently verified** external payments.
- Sales history, immutable receipt snapshots, browser printing / Save as PDF, suspended carts for the current browser session.
- Controlled partial returns, cash/manual external refund allocations, and restock versus damaged disposition.
- Register opening/closing, cash-only reconciliation, and manager/owner approval of explained variances.
- Daily sales, refunds, tax, cost of goods, gross profit, low-stock count, payment breakdown, and CSV export.
- User creation, password recovery through a local administrator command, audit viewer.
- Database migrations, SQLite functional tests, PostgreSQL concurrency tests, frontend tests, and GitHub Actions.
- Streaming encrypted PostgreSQL backup, restore to an empty database, and retryable S3-compatible upload.

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
  scripts/             Windows setup/startup and encrypted backup tooling
  docs/                Architecture, module guides, API, security and release limits
```

See [architecture and schema](docs/ARCHITECTURE.md), [inventory](docs/INVENTORY.md), [checkout and payments](docs/PAYMENTS.md), [API reference](docs/API.md), [Windows operations](docs/WINDOWS.md), and [backup / restore](docs/BACKUP.md).

## Windows installer (recommended for the shop computer)

A self-contained Windows x64 installer is now available through the **Windows installer** GitHub Actions workflow. It includes Python, the built interface and a private PostgreSQL instance. Open the DATUS shortcut and use the graphical first-run wizard to create your shop and owner account; no developer tools or separate database installation are needed.

See [installer instructions](docs/INSTALLER.md) for downloads, checksums, data locations, upgrades and uninstall behavior. Current builds are unsigned. Your business database and backups are stored outside the application directory and retained when uninstalling.

The commands below are the alternative developer/manual installation, not required when using the installer.

## Manual Windows 11 installation

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
3. Add a supplier and purchase order. Enter quantities and costs in **base units**.
4. When goods arrive, post the delivered quantities. Only receiving increases inventory.
5. Open **Cash register** and enter the physical opening float.
6. Open **New sale**, select retail or wholesale mode, and search or scan products. Barcode scanners must act as a keyboard and send Enter.
7. Check the server-calculated total. Enter payments equal to the amount due. For cash, record the amount retained **after giving change**.
8. Complete the sale and print its receipt or save it as PDF. Use **Sales history** to reprint it later.
9. Review **Daily reports**, reconcile the inventory ledger, and close the register with counted cash.
10. Run the encrypted backup and confirm off-device upload when configured.

Example: a carton contains 12 units. Retail is KES 10 per unit, wholesale is KES 110 per carton. Selling two cartons reduces stock by 24 units and charges KES 220 before configured tax. Prices and pack conversion are copied into sale lines, so editing the product later does not alter the receipt.

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
