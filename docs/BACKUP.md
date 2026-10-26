# Encrypted backup and restoration

Backups are separate from transaction synchronization. The Windows PostgreSQL database remains authoritative. Internet failure must not stop cash sales. A failed cloud upload leaves the encrypted file queued locally and returns a failure exit code for monitoring.

## Configure

Use a PostgreSQL `pg_dump` version matching or newer than the server. Put PostgreSQL `bin` in PATH or set `PG_DUMP` and `PG_RESTORE` to complete executable paths in `.env`.

Create a key file outside the repository in a Windows folder accessible only to the operator account. Do not store it in the cloud backup bucket. The keygen command refuses to overwrite an existing file:

```powershell
.\.venv\Scripts\python.exe scripts\backup.py keygen --key-file 'C:\SecureDatus\backup.key'
```

The parent directory must already exist. Restrict its ACL and preserve a separate offline recovery copy. Losing this key makes encrypted backups unrecoverable. Set `.env`:

```text
BACKUP_KEY_FILE=C:/SecureDatus/backup.key
BACKUP_BUCKET=your-private-backup-bucket
BACKUP_PREFIX=datus/shop-01
# Optional S3-compatible endpoint; leave empty for AWS S3.
BACKUP_ENDPOINT_URL=
```

Use the AWS SDK's normal credential chain for cloud access. Prefer a dedicated principal restricted to the backup prefix and upload operations. Never commit access keys. The bucket is not created automatically. Enable private access, versioning and a lifecycle policy appropriate to the business. No cloud service is provisioned by this repository.

## Back up and retry upload

```powershell
.\.venv\Scripts\python.exe scripts\backup.py backup
.\.venv\Scripts\python.exe scripts\backup.py backup --upload
.\.venv\Scripts\python.exe scripts\backup.py upload
```

The backup flow uses `pg_dump --format=custom --no-owner --no-acl`. It encrypts in bounded 1 MiB chunks with AES-256-GCM, a random file nonce and sequential chunk counters. Header/counter authentication and a final authenticated empty frame detect tampering, reorder and truncation. It decrypts the produced file for authentication verification before publishing the `.dump.enc` name. This verifies the encrypted envelope, not database restorability; restoration must also be exercised.

Temporary plaintext files exist in a temporary subfolder under `backups/` during creation/verification/restoration and are removed on normal exit. Protect the local volume with BitLocker and restrict backup-folder permissions. After power loss, inspect and remove abandoned plaintext temporary folders only after verifying a complete encrypted backup. Encryption does not protect a running compromised Windows account that can read the key.

Cloud upload retries all complete files lacking an `.uploaded` marker. It uses the same object key for retries, avoiding multiple names for the same file. Markers indicate successful upload, not permanent remote availability. Periodically verify object existence and restore from downloaded copies.

Local retention is intentionally manual: the script never deletes your completed backups. Configure cloud lifecycle retention and a documented local retention policy; monitor disk space. Do not delete the only off-device recovery copy.

## Restore drill

1. Stop work on a failed installation; preserve its files and database for investigation.
2. Create a new, empty PostgreSQL database with a compatible server version.
3. Obtain the encrypted backup and correct key through your recovery process.
4. Set `RESTORE_DATABASE_URL` to the **new empty database**, then restore:

```powershell
$env:RESTORE_DATABASE_URL = 'postgresql+psycopg://RESTORE_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/datus_restore_test'
.\.venv\Scripts\python.exe scripts\backup.py restore --file 'C:\DatusRecovery\BACKUP_FILE.dump.enc'
```

The tool refuses nonempty target databases. Restore uses one transaction and exits on the first error. It does not drop or clean an existing database. It also does not install PostgreSQL, rotate keys, or change DATUS configuration automatically.

5. Point a test DATUS instance at the restored database, run `db upgrade`, then `flask ... reconcile`.
6. Compare selected historic receipts, payment totals, last posted sale, stock balances and cash-session records.
7. Log the backup date, restoration date, verified checks, recovery time and potential data-loss interval.
8. Only after verification, switch the live `.env` to the recovered database.

Schedule a restore drill monthly and after material schema/backup changes. Daily backups imply up to one day's transactions may be lost if the computer fails before the next successful off-device backup; schedule more frequently if the business needs a shorter recovery point.

## Scheduling

In Windows Task Scheduler, create a task under the account with database/key/cloud access. Use the venv `python.exe`, arguments `scripts\backup.py backup --upload`, and Start in the DATUS folder. Choose a frequency, enable retry after failure, retain task history, and review nonzero exit codes. Existing cloud credentials may depend on interactive login; validate under the actual scheduled identity.

Cloud upload/retention settings require your bucket and credentials. The delivered code does not claim that a live cloud backup has occurred.
