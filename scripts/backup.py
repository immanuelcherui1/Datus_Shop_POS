"""Encrypted, retryable PostgreSQL backup. See docs/BACKUP.md before first use."""
import argparse
import base64
import os
import secrets
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'DATUSBK1'
CHUNK = 1024 * 1024


def encrypt(source, target, key):
    nonce = secrets.token_bytes(8)
    header = MAGIC + nonce
    cipher = AESGCM(key)
    with open(source, 'rb') as src, open(target, 'xb') as dst:
        dst.write(header)
        index = 0
        while True:
            chunk = src.read(CHUNK)
            counter = struct.pack('>I', index)
            encrypted = cipher.encrypt(nonce + counter, chunk, header + counter)
            dst.write(struct.pack('>I', len(encrypted)))
            dst.write(encrypted)
            if not chunk:
                break  # Authenticated empty final frame detects truncation, even at chunk boundaries.
            index += 1


def decrypt(source, target, key):
    cipher = AESGCM(key)
    with open(source, 'rb') as src, open(target, 'xb') as dst:
        header = src.read(16)
        if len(header) != 16 or not header.startswith(MAGIC):
            raise ValueError('Not a DATUS encrypted backup.')
        index = 0
        while True:
            length = src.read(4)
            if len(length) != 4: raise ValueError('Truncated backup.')
            size = struct.unpack('>I', length)[0]
            if size < 16 or size > CHUNK + 16: raise ValueError('Invalid encrypted frame.')
            encrypted = src.read(size)
            if len(encrypted) != size: raise ValueError('Truncated backup.')
            counter = struct.pack('>I', index)
            chunk = cipher.decrypt(header[8:] + counter, encrypted, header + counter)
            if not chunk:
                if src.read(1): raise ValueError('Unexpected trailing backup data.')
                break
            dst.write(chunk)
            index += 1


def pg_environment(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql': raise ValueError('Backups require PostgreSQL.')
    env = os.environ.copy()
    env.update(PGHOST=parsed.host or '127.0.0.1', PGPORT=str(parsed.port or 5432),
               PGUSER=parsed.username or '', PGPASSWORD=parsed.password or '', PGDATABASE=parsed.database or '')
    return env


def run_pg(command, env):
    result = subprocess.run(command, env=env, capture_output=True)
    if result.returncode:
        # Do not echo connection details or SQL data to scheduled-task logs.
        raise RuntimeError(f'{Path(command[0]).name} failed with exit code {result.returncode}; check database access and binary version.')


def upload_pending(directory):
    import boto3
    bucket = os.getenv('BACKUP_BUCKET')
    if not bucket: raise ValueError('Set BACKUP_BUCKET before requesting upload.')
    client = boto3.client('s3', endpoint_url=os.getenv('BACKUP_ENDPOINT_URL') or None)
    for file in sorted(directory.glob('*.dump.enc')):
        marker = file.with_suffix(file.suffix + '.uploaded')
        if marker.exists(): continue
        object_key = os.getenv('BACKUP_PREFIX', 'datus').strip('/') + '/' + file.name
        # Repeated upload uses the same object key. Failed uploads remain queued locally.
        client.upload_file(str(file), bucket, object_key)
        marker.write_text(object_key, encoding='utf-8')
        print(f'Uploaded encrypted backup: {file.name}')


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['keygen', 'backup', 'upload', 'restore'])
    parser.add_argument('--key-file', default=os.getenv('BACKUP_KEY_FILE'))
    parser.add_argument('--directory', type=Path, default=ROOT / 'backups')
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--target-url-env', default='RESTORE_DATABASE_URL', help='Name of environment variable containing EMPTY target database URL')
    args = parser.parse_args()
    if args.action == 'upload':
        upload_pending(args.directory)
        return
    if not args.key_file: raise ValueError('Set BACKUP_KEY_FILE or --key-file.')
    key_path = Path(args.key_file)
    if args.action == 'keygen':
        with key_path.open('xb') as stream: stream.write(base64.urlsafe_b64encode(AESGCM.generate_key(256)))
        print('Backup key created. Protect it with Windows permissions and keep a separate recovery copy.')
        return
    key = base64.urlsafe_b64decode(key_path.read_bytes().strip())
    if len(key) != 32: raise ValueError('Expected a 256-bit backup key.')
    args.directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='datus-backup-', dir=args.directory) as temp:
        dump = Path(temp) / 'database.dump'
        if args.action == 'backup':
            env = pg_environment(os.environ['DATABASE_URL'])
            run_pg([os.getenv('PG_DUMP', 'pg_dump'), '--format=custom', '--no-owner', '--no-acl', '--file', str(dump)], env)
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(4) + '.dump.enc'
            final = args.directory / name
            pending = final.with_suffix('.partial')
            try:
                encrypt(dump, pending, key)
                # Verify authentication before marking the encrypted file complete.
                verified = Path(temp) / 'verified.dump'
                decrypt(pending, verified, key)
                if verified.stat().st_size != dump.stat().st_size: raise RuntimeError('Verification failed.')
                pending.replace(final)
            finally:
                pending.unlink(missing_ok=True)
            print(f'Created verified encrypted backup: {final.name}')
        else:
            if not args.file: raise ValueError('Restore requires --file.')
            target = os.environ[args.target_url_env]
            env = pg_environment(target)
            import psycopg
            with psycopg.connect(host=env['PGHOST'], port=env['PGPORT'], user=env['PGUSER'],
                                password=env['PGPASSWORD'], dbname=env['PGDATABASE']) as conn:
                count = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')").fetchone()[0]
                if count: raise ValueError('Restore target must be an empty database. Existing databases are never overwritten.')
            decrypt(args.file, dump, key)
            run_pg([os.getenv('PG_RESTORE', 'pg_restore'), '--dbname', env['PGDATABASE'], '--no-owner', '--no-acl',
                    '--exit-on-error', '--single-transaction', str(dump)], env)
            print('Restored into the empty target database. Run migrations, reconciliation, and receipt checks before switching.')
    if args.action == 'backup' and args.upload: upload_pending(args.directory)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Backup operation failed ({type(error).__name__}). {error if isinstance(error, (ValueError, RuntimeError)) else "Check configuration, credentials, connectivity, and key access."}')
        raise SystemExit(1)
