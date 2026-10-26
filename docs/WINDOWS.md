# Windows operations

For the self-contained desktop installer, follow [INSTALLER.md](INSTALLER.md). The steps below are for a manual source deployment with separately installed developer tools and PostgreSQL.

## Runtime

PostgreSQL runs as its installed Windows service. DATUS uses Waitress, which supports Windows, bound to `127.0.0.1:8080`. The browser opens that address. Node and Vite are build tools, not production servers. Windows must remain powered and awake while trading.

`scripts/start.ps1` runs in the foreground. Optional `scripts/register-startup.ps1` creates a Task Scheduler entry that starts `pythonw.exe backend/run.py` at user sign-in. It refuses to replace an existing task. It is **not a Windows service** and does not start before sign-in. Inspect the task in Task Scheduler and test it after reboot. Stop the task/process before applying updates.

Avoid simultaneously starting a foreground instance and startup task on the same port. PostgreSQL must be available before application startup. Visit `/api/health` to confirm the service and database respond.

## Updating

1. Finish or suspend checkout and close the register if appropriate.
2. Create and verify an encrypted backup and ensure a recovery key exists off-device.
3. Stop the DATUS server.
4. Pull the reviewed release; review migrations and release limitations.
5. Install pinned Python requirements and `npm ci`, then build the frontend.
6. Run `flask --app backend/datus db upgrade`.
7. Run reconciliation, start the server, and verify login, stock and a historical receipt.

Do not downgrade financial-schema migrations casually. Restore a verified pre-update backup into a separate database if rollback is necessary.

## Troubleshooting

| Symptom | Check |
|---|---|
| Browser cannot connect | DATUS process running, loopback port 8080 available, correct address |
| Database unavailable | PostgreSQL service, `.env` URL, password encoding, database role |
| Startup rejects secret | Run configure once or generate two distinct random 32+ character secrets |
| Login fails | Correct username/password; owner bootstrapped; wait after rate limit |
| CSRF/session error | Sign in again; cookies enabled; use the same hostname consistently |
| Cannot complete cash sale | Open register, sufficient stock, exact payment total |
| Duplicate SKU/reference | Use the existing product/payment; inspect history before retrying |
| Receipt blank or wrong paper | Browser print preview, printer driver, 80 mm paper, disable browser headers/footers |
| Backup upload fails | Local encrypted backup remains; check internet, bucket, SDK credentials and scheduled identity |
| Vite config error on restricted Windows | Project uses native config loading; use supported Node 22.12+ / 24 |

## Recovery access

An authorized local administrator can reset a user password through an interactive command:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend/datus reset-password
```

This invalidates the user's previous tokens and writes an audit event. Local administrative access is powerful: protect the Windows login and database configuration. There is no emailed password reset, because the shop does not depend on cloud identity.

## Hardware acceptance

Test your actual keyboard barcode scanner, receipt printer, display scaling, power-failure recovery, disk space and UPS. Browser receipt printing is implemented; direct ESC/POS, cash-drawer opening and fiscal printer integrations are not. Do not enable network access for Android by merely changing HOST; add TLS and device access controls first.
