# Implementation status and verification

## Delivered scope

Authentication/authorization, product catalogue, stock ledger and reconciliation, suppliers, purchase orders and partial receiving, retail/wholesale checkout, split recorded settlement, receipts, controlled returns, register reconciliation, daily reports, user creation, audit view, migrations, Windows scripts and encrypted backup tooling are implemented. The desktop packaging workflow bundles Python, PostgreSQL and the frontend, with a graphical owner setup and per-user installer.

The frontend talks to the actual Flask API. Empty screens do not insert fabricated business metrics. Demonstration catalogue data is optional and starts with zero stock.

## Verification record

Local verification performed during implementation:

- SQLite: 14 tests passed; 2 PostgreSQL-only concurrency cases intentionally skipped.
- PostgreSQL 17.6 on Windows: all 16 tests passed, including simultaneous last-unit checkout and simultaneous identical-key checkout.
- React Testing Library / Vitest: 5 tests passed (failed login, retry-key persistence, reload recovery, definite rejection recovery, and barcode/search race).
- Vite production build passed.
- Windows installer acceptance passed on GitHub Actions: bundled resource/Tcl checks, silent installation, first-run owner and schema setup, wholesale checkout, stock/cash reconciliation, encrypted backup, restart preserving credentials and receipts, restricted database permissions, and uninstall preserving business data. Verified run: https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/40411121934 (commit f4d1023).
- Local frozen backend smoke passed. The local sandbox prevented Tcl initialization and restricted-token PostgreSQL startup; the delivered installer was built and tested on the separate Windows runner.
- Browser smoke test: owner login, opening-stock adjustment, register opening, wholesale checkout and receipt rendering. One pack consumed 12 base units and the receipt retained its wholesale price.
- Real PostgreSQL backup/restore drill passed: encrypted dump restored into a new empty database, historical receipt matched, inventory reconciled and expected cash matched. A second restore into the populated database was correctly refused.

See GitHub Actions for verification on subsequent commits. The repository's PostgreSQL tests deliberately skip if a test database is not configured; SQLite alone does not establish concurrency safety.

Acceptance tests include product uniqueness, purchasing vs receipt distinction, sale stock consumption, full rollback after a late injected failure, idempotency, insufficient stock, wholesale conversion, over-return prevention, refund traceability, immutable SQL/ORM ledger, permission and branch denial, split settlement, cash reconciliation, balance reconciliation, historical prices, external reference duplication, daily profit/tax, and CSRF/session revocation.

Cloud credentials, a real receipt printer, real scanner and production payment provider were not available for verification. Their acceptance must be completed on the installed shop computer. No live cloud upload was performed.

## Known limitations

- Single business and one operating branch; no organization/branch administration, warehouse transfers or multi-tenant isolation product.
- No independently offline Android/device synchronization. The Windows database is authoritative; browser caching is not used as a second ledger.
- No Android APK yet. API boundaries permit a future mobile client after secure LAN access is designed.
- No live Daraja/card/bank initiation, webhook verification or provider reconciliation. External settlement is a privileged manual record only.
- No credit balances, customer accounts, loyalty, expenses module, supplier payable ledger or full accounting journal.
- Tax-exclusive pricing only; tax rate configured per product. No fiscal/e-invoicing integration or legal certification.
- No batch-based expiry, serials, reservations or formal physical-count workflow. Product-level earliest expiry is a manually maintained indicator.
- Product names, categories and suppliers are business-wide. Customer is an optional name snapshot, not a full customer profile.
- Return entry requires operator-entered refund allocations; the server validates exact eligibility and rounded totals. No exchange wizard.
- Suspended carts use browser sessionStorage and are not durable after browser session loss. Pending checkout requests and keys survive navigation/refresh in sessionStorage and must be recovered before a different checkout. Closing the browser session or clearing storage can still lose that record; inspect sales before repeating.
- Product selectors show up to 100 search results; search by name/SKU to find additional products. Dashboard insight lists are not paginated.
- Browser receipt print/PDF only; no direct ESC/POS, drawer pulse or fiscal printer driver.
- The installer offers an optional sign-in shortcut and a desktop controller. Manual source deployments can use the scheduled startup script. Neither is an installed Windows service. Backup scheduling and the cloud bucket require operator configuration.
- Installer builds are unsigned until a publisher certificate is configured.
- Cloud retention/local cleanup and remote availability monitoring are operational configuration, not automatic deletion jobs.
- Backup key and application/database credentials require secure local storage and separate recovery copies.
- Login throttling is process-local. No central alerting, distributed job worker or MFA.
- Audit history is protected against ordinary application modification, not a hostile machine/database administrator.
- PostgreSQL is required for deployment. SQLite is only a development/test convenience.

## Next milestones

1. Complete shop hardware, tax, backup restore and staff acceptance on the target Windows computer.
2. Improve large-catalogue selectors and extend recovery beyond browser-session storage.
3. Add verified provider integration and reconciliation against real sandbox accounts.
4. Add batch/expiry or credit/accounting only when business requirements justify them.
5. Add secure Android LAN client, then design separate-device offline operation if required.

## Remote access update — 29 October 2026

DATUS 0.2.2 adds opt-in Tailscale Funnel configuration for a separate secured loopback listener. Local tests: 33 passed, 2 PostgreSQL-only tests skipped. GitHub integrity and Windows installer acceptance passed at commit 738115c (https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/40948484361). PowerShell parsing, CLI argument forwarding and occupied-listener checks also passed locally. Tests verify HTTPS cookie policy, origin/host checks, CSRF, login/logout, forwarded-header throttling, and a real second HTTP listener in the frozen package. Live tailnet approval and public mobile access remain shop-computer acceptance steps; no public endpoint was enabled during preparation. See REMOTE_ACCESS.md.

## Wholesale/retail amendments — 30 October 2026

Version 0.3.0 adds a shared inventory with wholesale/retail allocations, four selling modes, purchase draft editing/confirmation and print/PDF, supplier editing, actual receipt costs, catalogue suggestions, receipt accountability, session history and M-Pesa reconciliation, and interactive dashboard charts/stock lists. See [AMENDMENTS.md](AMENDMENTS.md) for migration requirements and precise limits. Verification is in progress; check the latest CI run before deployment.
