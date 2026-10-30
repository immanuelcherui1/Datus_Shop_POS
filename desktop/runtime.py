"""Private PostgreSQL lifecycle and first-run setup for the Windows desktop installer.

No Python/Node/PostgreSQL installation is required on the user's computer. Database
files, credentials and backups belong to the user data directory, never the app folder.
"""
import ctypes
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql
from dotenv import dotenv_values, load_dotenv
from werkzeug.security import generate_password_hash
from datus.paths import resource_root, data_root

_version_file = resource_root() / 'version.txt'
VERSION = _version_file.read_text(encoding='utf-8').strip() if _version_file.exists() else '0.3.0'


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def exclusive_json(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream)


class Installation:
    def __init__(self, directory=None, postgres=None):
        self.data = Path(directory) if directory else data_root()
        self.resources = resource_root()
        self.pg = Path(postgres) if postgres else self.resources / 'postgresql' / 'bin'
        self.cluster = self.data / 'database'
        self.marker = self.data / 'owner.ready'
        self.settings_path = self.data / 'database-admin.json'
        self.settings = None
        self.process = None
        self.server = None
        self.application = None
        self.log_handle = None
        self.stopping = threading.Event()
        self.server_thread = None
        self.web_servers = []
        self.remote_config = None
        self.remote_application = None

    def configure(self, business_name):
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / 'logs').mkdir(exist_ok=True)
        os.environ['DATUS_DATA_DIR'] = str(self.data)
        if not self.settings_path.exists():
            exclusive_json(self.settings_path, {'database_port': available_port(), 'http_port': available_port(),
                'owner_password': secrets.token_hex(32), 'app_password': secrets.token_hex(32)})
        self.settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        env_file = self.data / '.env'
        if not env_file.exists():
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import base64
            key_path = self.data / 'backup.key'
            if not key_path.exists():
                with key_path.open('xb') as stream: stream.write(base64.urlsafe_b64encode(AESGCM.generate_key(256)))
            # JSON quoting is also valid for these dotenv double-quoted string values.
            values = {'DATABASE_URL': self.url('datus_app', self.settings['app_password']),
                'SECRET_KEY': secrets.token_hex(32), 'JWT_SECRET_KEY': secrets.token_hex(32),
                'BUSINESS_NAME': business_name, 'CURRENCY': 'KES', 'BUSINESS_TIMEZONE': 'Africa/Nairobi',
                'COOKIE_SECURE': 'false', 'HOST': '127.0.0.1', 'PORT': str(self.settings['http_port']),
                'BACKUP_KEY_FILE': key_path.as_posix(), 'PG_DUMP': (self.pg / 'pg_dump.exe').as_posix(),
                'PG_RESTORE': (self.pg / 'pg_restore.exe').as_posix(), 'BACKUP_BUCKET': '', 'BACKUP_PREFIX': 'datus'}
            with env_file.open('x', encoding='utf-8') as stream:
                stream.write('\n'.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in values.items()) + '\n')
        load_dotenv(env_file, override=True)
        # Upgrades may move the binary directory; keep the current installed tools authoritative.
        os.environ['PG_DUMP'] = str(self.pg / 'pg_dump.exe')
        os.environ['PG_RESTORE'] = str(self.pg / 'pg_restore.exe')

    def url(self, user, password):
        return f'postgresql+psycopg://{user}:{quote(password, safe="")}@127.0.0.1:{self.settings["database_port"]}/datus'

    def connect(self, database='postgres', autocommit=True):
        return psycopg.connect(host='127.0.0.1', port=self.settings['database_port'], user='datus_owner',
            password=self.settings['owner_password'], dbname=database, connect_timeout=2, autocommit=autocommit)

    def external(self, command, *, background=False, timeout=90):
        # Frozen Python's DLL directory must not leak into PostgreSQL's own dependencies.
        frozen_windows = os.name == 'nt' and getattr(sys, 'frozen', False)
        if frozen_windows: ctypes.windll.kernel32.SetDllDirectoryW(None)
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        try:
            if background:
                return subprocess.Popen(command, stdout=self.log_handle, stderr=self.log_handle, **flags)
            result = subprocess.run(command, stdout=self.log_handle, stderr=self.log_handle, timeout=timeout, **flags)
            if result.returncode:
                raise RuntimeError(f'{Path(command[0]).name} failed. See the local database log; existing data was preserved.')
        finally:
            if frozen_windows: ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)

    def start_database(self):
        if not (self.pg / 'postgres.exe').is_file():
            raise RuntimeError('The bundled PostgreSQL files are missing. Reinstall DATUS; keep the business data folder.')
        self.log_handle = (self.data / 'logs' / 'postgresql.log').open('a', encoding='utf-8')
        if not (self.cluster / 'PG_VERSION').exists():
            if self.cluster.exists() and any(self.cluster.iterdir()):
                raise RuntimeError('Database initialization was interrupted. Preserve this data folder and request recovery assistance.')
            password_file = self.data / '.init-password'
            try:
                with password_file.open('x', encoding='utf-8') as stream: stream.write(self.settings['owner_password'])
                self.external([str(self.pg / 'initdb.exe'), '-D', str(self.cluster), '-U', 'datus_owner',
                    '--auth=scram-sha-256', '--pwfile', str(password_file), '--encoding=UTF8', '--locale=C'])
            finally:
                password_file.unlink(missing_ok=True)
        if (self.cluster / 'PG_VERSION').read_text().strip() != '17':
            raise RuntimeError('This data directory requires a different PostgreSQL major version. No files were changed.')
        try:
            with self.connect() as connection:
                directory = connection.execute('SHOW data_directory').fetchone()[0]
                if Path(directory).resolve() != self.cluster.resolve():
                    raise RuntimeError('The configured port belongs to another database. DATUS will not use or stop it.')
                return
        except psycopg.OperationalError:
            pass
        # pg_ctl starts PostgreSQL with a restricted token on Windows, including
        # when an administrator launches DATUS. Direct postgres.exe would refuse it.
        self.external([str(self.pg / 'pg_ctl.exe'), '-D', str(self.cluster), '-w', '-t', '45',
            '-l', str(self.data / 'logs' / 'postgresql-server.log'),
            '-o', f"-h 127.0.0.1 -p {self.settings['database_port']}", 'start'])
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                with self.connect(): return
            except psycopg.OperationalError: time.sleep(.25)
        raise RuntimeError('Database startup timed out. Close DATUS and check the local database log.')

    def initialize(self, business_name, username=None, password=None):
        if not self.marker.exists() and (not username or not password or len(password) < 12):
            raise ValueError('First setup requires a username and a password of at least 12 characters.')
        self.configure(business_name)
        self.start_database()
        with self.connect() as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='datus_app'").fetchone():
                connection.execute(sql.SQL('CREATE ROLE datus_app LOGIN PASSWORD {}').format(sql.Literal(self.settings['app_password'])))
            if not connection.execute("SELECT 1 FROM pg_database WHERE datname='datus'").fetchone():
                connection.execute('CREATE DATABASE datus OWNER datus_owner')
        from datus import create_app
        from datus.extensions import db
        from datus.models import Branch, User
        from flask_migrate import upgrade
        from alembic.script import ScriptDirectory
        from sqlalchemy import select, text
        migration_app = create_app({'SQLALCHEMY_DATABASE_URI': self.url('datus_owner', self.settings['owner_password'])})
        with migration_app.app_context():
            exists = db.session.scalar(text("SELECT to_regclass('public.alembic_version')"))
            current = db.session.scalar(text('SELECT version_num FROM alembic_version')) if exists else None
            target = ScriptDirectory(str(self.resources / 'backend' / 'migrations')).get_current_head()
            db.session.rollback()
            if self.marker.exists() and current != target:
                self.backup()  # Do not migrate an existing shop unless an encrypted backup succeeds.
            upgrade()
            if not db.session.scalar(select(User.id).limit(1)):
                branch = Branch(name='Main shop')
                db.session.add(branch); db.session.flush()
                db.session.add(User(username=username, password_hash=generate_password_hash(password), role='owner', branch_id=branch.id))
                db.session.commit()
            db.session.remove(); db.engine.dispose()
        with self.connect('datus') as connection:
            connection.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
            connection.execute('GRANT CONNECT ON DATABASE datus TO datus_app')
            connection.execute('GRANT USAGE ON SCHEMA public TO datus_app')
            connection.execute('GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO datus_app')
            connection.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO datus_app')
            connection.execute('GRANT UPDATE ON supplier, product, stock, "user", purchase, purchase_line, cash_session, idempotency TO datus_app')
            connection.execute('GRANT DELETE ON purchase_line TO datus_app')
        self.marker.write_text('Owner initialized. Do not delete this file.\n', encoding='utf-8')
        self.application = create_app()

    @property
    def address(self):
        return f'http://127.0.0.1:{self.settings["http_port"]}'

    def start_server(self):
        from waitress import create_server
        from datus import create_app
        from datus.remote import validate_origin
        endpoints = [(self.application, self.settings['http_port'])]
        config_path = self.data / 'remote-access.json'
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding='utf-8-sig'))
            origin = validate_origin(config['origin'])
            port = config['port']
            if type(port) is not int or not 1024 <= port <= 65535 or port in (self.settings['http_port'], self.settings['database_port']):
                raise ValueError('Remote listener needs its own valid port.')
            self.remote_config = config
            self.remote_application = create_app({'REMOTE_ORIGIN': origin,
                'JWT_COOKIE_SECURE': True, 'JWT_COOKIE_CSRF_PROTECT': True,
                'JWT_ACCESS_COOKIE_NAME': 'datus_remote_access',
                'RATELIMIT_KEY_PREFIX': 'datus-remote'})
            endpoints.append((self.remote_application, port))
        self.stopping.clear()
        try:
            for application, port in endpoints:
                server = create_server(application, host='127.0.0.1', port=port, threads=8)
                def serve(server=server):
                    try:
                        server.run()
                    except OSError as error:
                        if not (self.stopping.is_set() and getattr(error, 'winerror', None) == 10038):
                            raise
                thread = threading.Thread(target=serve, daemon=True, name=f'DATUS web {port}')
                self.web_servers.append((server, thread))
                thread.start()
            self.server, self.server_thread = self.web_servers[0]
        except Exception:
            self.stop_web_servers()
            raise

    def stop_web_servers(self):
        self.stopping.set()
        for server, thread in self.web_servers:
            server.close()
            server.task_dispatcher.shutdown(cancel_pending=False, timeout=15)
            thread.join(timeout=5)
        self.web_servers.clear()
        self.server = None

    def backup(self):
        from scripts.backup import main
        main(['backup'])

    def stop(self):
        self.stop_web_servers()
        from datus.extensions import db
        for application in (self.application, self.remote_application):
            if application:
                with application.app_context():
                    db.session.remove(); db.engine.dispose()
        if self.settings and (self.cluster / 'postmaster.pid').exists():
            # Verify ownership by credentials and data_directory before stopping any server.
            with self.connect() as connection:
                if Path(connection.execute('SHOW data_directory').fetchone()[0]).resolve() != self.cluster.resolve():
                    raise RuntimeError('Database ownership verification failed; server was not stopped.')
            self.external([str(self.pg / 'pg_ctl.exe'), '-D', str(self.cluster), '-m', 'fast', '-w', 'stop'])
        if self.log_handle:
            self.log_handle.close(); self.log_handle = None
