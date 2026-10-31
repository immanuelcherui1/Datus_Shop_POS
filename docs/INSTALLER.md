# Windows installer

The desktop installer packages DATUS, Python, the built React interface, PostgreSQL 17.11 and required libraries. The shop computer does not need Node, Python, Git or a separately installed PostgreSQL service. Installation and trading work offline after the installer has been downloaded.

## Operator setup

1. Run `DATUS-Setup-0.4.0-x64.exe` on 64-bit Windows 11 under the Windows account that will run the shop.
2. Choose whether to create a desktop shortcut and whether to open DATUS at sign-in.
3. Open **DATUS** from the desktop or Start menu.
4. Enter the business name, owner username and a password of at least 12 characters. There are no default credentials.
5. Wait for the private database and schema to initialize. The browser opens the shop workspace.
6. Sign in with the owner account you just created. Follow the first trading session steps in README.

Keep the DATUS controller window open while trading. Closing it asks for confirmation, stops the web server and shuts down the private database. Opening the shortcut again starts the same shop and preserves accounts, receipts and inventory. A second shortcut launch opens the existing workspace instead of starting another database.

The controller also has **Create encrypted backup** and **Open data and backups folder** buttons. Keep an off-device copy of backups and the recovery key. Cloud upload still requires your storage configuration; the installer does not create a paid cloud account.

## Files and upgrades

- Installed application: `%LOCALAPPDATA%\Programs\DATUS`
- Business data and settings: `%LOCALAPPDATA%\DATUS`
- PostgreSQL data: `%LOCALAPPDATA%\DATUS\database`
- Logs: `%LOCALAPPDATA%\DATUS\logs`
- Encrypted backups: `%LOCALAPPDATA%\DATUS\backups`
- Backup key: `%LOCALAPPDATA%\DATUS\backup.key`

The configuration and database administrator file contain secrets. Protect the Windows account, keep local-volume encryption enabled, and keep the recovery key separate from off-device backup files. The app uses a restricted database role; only the launcher uses the migration owner to initialize or upgrade the schema.

**For the 0.3.0 upgrade, first close all trading sessions in the previous version and take a backup.** Existing stock starts in wholesale; allocate retail shelf stock before retail checkout. See [AMENDMENTS.md](AMENDMENTS.md). Close DATUS before running a replacement installer. The installer refuses to update or uninstall while its desktop controller is running. It replaces application files and keeps the business-data folder. Before applying a newer schema, the launcher creates an encrypted backup and aborts the upgrade if backup fails.

**Uninstall removes the application and shortcuts, not shop data or backups.** Reinstalling under the same Windows account reconnects to the preserved shop. Do not manually remove the business-data folder unless you have intentionally retired the shop and verified recoverable backups.

This is a per-user application, not a Windows service. The optional sign-in shortcut starts after that account signs in. Different Windows accounts have different data folders; use the designated shop account consistently.

## Download and verify

GitHub Actions produces `DATUS-Windows-x64-installer` artifacts for installer-related commits. Download the installer and its `.sha256` file from a successful **Windows installer** run. Version tags publish the same files as GitHub Release assets after the packaged smoke test passes.

```powershell
Get-FileHash .\DATUS-Setup-0.4.0-x64.exe -Algorithm SHA256
```

Compare the result with the accompanying checksum. Current builds are **unsigned** because no publisher code-signing certificate has been configured. Windows may show an unknown-publisher warning. Verify the file's source and checksum; do not turn off Windows security protections. Signing and clean-machine acceptance remain release tasks before broad shop deployment.

## Build from source

On Windows x64 with Python 3.12 and Node 22.12+:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
.\.venv\Scripts\python.exe packaging\build_installer.py
```

The build downloads official PostgreSQL and NSIS archives, verifies pinned SHA-256 digests, builds the frontend, freezes the Python application, checks required resources and compiles the installer. It never bundles `.env`, a business database, backup keys or working test data. Build outputs are ignored by Git and placed in `release/`.

The frozen smoke test runs in a newly created empty directory and exercises owner bootstrap, migrations, actual application authentication, wholesale/retail checkout, stock allocation, Cash/M-Pesa reconciliation, supplier edits, draft confirmation, encrypted backup and restart without changing existing business data. GitHub's Windows job runs this test before uploading artifacts.

Maintainers must review and update pinned tool URLs/digests when upgrading PostgreSQL or the installer compiler. The PostgreSQL major version is fixed at 17; a future major-version upgrade needs a separate data migration plan.

Build references: [PyInstaller runtime paths](https://www.pyinstaller.org/en/stable/runtime-information.html), [NSIS downloads](https://nsis.sourceforge.io/Download), [PostgreSQL 17.11 release notes](https://www.postgresql.org/docs/release/17.11/). These explain packaging choices; test results are recorded separately in STATUS.md.

## Verified 0.4.0 build

[Download Windows installer](https://github.com/immanuelcherui1/Datus_Shop_POS/actions/runs/41144625437/artifacts/13020660340). Includes the supplied branding, light/dark appearance and [shop workflow refinements](SHOP-WORKFLOWS.md). GitHub sign-in may be required. The artifact includes executable checksum and smoke-test results. The 0.3.0 migration precautions above apply when upgrading from older releases. Version 0.4.0 adds migration 0004 for money workflows and purchase conversion snapshots. Existing purchases retain an unknown payment status; new orders support payment tracking. Back up and close DATUS before installing. See [workflow integrity and upgrade handling](WORKFLOW-INTEGRITY.md).
