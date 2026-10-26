"""Automated frozen-application acceptance without using the operator's business data."""
import json
import os
import secrets
from pathlib import Path
from datus.paths import resource_root


def resource_check():
    root = resource_root()
    for path in ['frontend/dist/index.html', 'backend/migrations/env.py',
                 'backend/migrations/versions/0001_initial_datus_transaction_schema.py', 'postgresql/bin/postgres.exe']:
        if not (root / path).is_file(): raise RuntimeError(f'Missing packaged resource: {path}')
    import psycopg
    import tkinter
    interpreter = tkinter.Tcl()
    assert interpreter.eval('info patchlevel')
    from sqlalchemy.dialects.postgresql import psycopg as dialect
    from scripts.backup import encrypt, decrypt
    return True


def smoke_test(directory):
    if directory.exists() and any(directory.iterdir()):
        raise RuntimeError('Smoke tests require a new empty directory. Existing data is never overwritten.')
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['DATUS_DATA_DIR'] = str(directory)
    log = (directory / 'smoke.log').open('a', encoding='utf-8')
    import sys
    if sys.stdout is None: sys.stdout = log
    if sys.stderr is None: sys.stderr = log
    from desktop.runtime import Installation
    installation = Installation(directory, postgres=os.getenv('DATUS_POSTGRES_BIN'))
    password = secrets.token_urlsafe(24)
    try:
        installation.initialize('DATUS installer test', 'installer-test', password)
        installation.start_server()
        client = installation.application.test_client()
        assert client.get('/').status_code == 200
        assert client.post('/api/auth/login', json={'username': 'installer-test', 'password': password}).status_code == 200
        def post(path, data):
            response = client.post('/api' + path, json=data, headers={'Idempotency-Key': secrets.token_hex(16),
                'X-CSRF-TOKEN': client.get_cookie('csrf_access_token').value})
            assert response.status_code == 200, response.json
            return response.json
        product = post('/products', {'sku': 'INSTALLER-TEST', 'name': 'Installer test item',
            'retail_price': '10', 'wholesale_price': '110', 'pack_size': '12'})
        post('/inventory/adjustments', {'product_id': product['id'], 'quantity': '24', 'unit_cost': '5', 'reason': 'Installer smoke test'})
        post('/register/open', {'opening': '100'})
        sale = post('/sales', {'lines': [{'product_id': product['id'], 'quantity': '1', 'mode': 'wholesale'}],
            'payments': [{'method': 'cash', 'amount': '110'}]})
        assert client.get('/api/inventory/reconciliation').json['ok']
        assert client.get('/api/register').json['expected'] == '210.00'
        snapshot = client.get(f"/api/sales/{sale['id']}").json
        installation.backup()
        assert list((directory / 'backups').glob('*.dump.enc'))
        installation.stop()
        restarted = Installation(directory, postgres=os.getenv('DATUS_POSTGRES_BIN'))
        installation = restarted
        restarted.initialize('This must not overwrite the existing shop')
        restarted.start_server()
        client = restarted.application.test_client()
        assert client.post('/api/auth/login', json={'username': 'installer-test', 'password': password}).status_code == 200
        assert client.get(f"/api/sales/{sale['id']}").json == snapshot
        assert client.get('/api/auth/me').json['business_name'] == 'DATUS installer test'
        with restarted.connect('datus') as connection:
            privileges = connection.execute("SELECT has_table_privilege('datus_app','movement','UPDATE'), has_table_privilege('datus_app','movement','DELETE')").fetchone()
            assert privileges == (False, False)
        (directory / 'smoke-result.json').write_text(json.dumps({'ok': True, 'checks': [
            'first-run migrations', 'owner creation', 'static frontend', 'cookie authentication', 'wholesale checkout',
            'stock reconciliation', 'cash reconciliation', 'encrypted backup', 'restart preserves data and credentials',
            'restricted runtime database permissions']}), encoding='utf-8')
    finally:
        installation.stop()
