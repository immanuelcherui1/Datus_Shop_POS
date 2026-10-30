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
        from desktop.runtime import available_port
        remote_port = available_port()
        while remote_port in (installation.settings['http_port'], installation.settings['database_port']):
            remote_port = available_port()
        (directory / 'remote-access.json').write_text(json.dumps({'origin': 'https://datus.smoke.ts.net', 'port': remote_port}), encoding='utf-8')
        installation.start_server()
        # Exercise the real separate HTTP listener as the TLS proxy would reach it.
        import urllib.request
        request = urllib.request.Request(f'http://127.0.0.1:{remote_port}/api/health', headers={'Host': 'datus.smoke.ts.net'})
        with urllib.request.urlopen(request, timeout=10) as response:
            assert json.load(response)['remote_access'] is True
        assert installation.remote_application.config['JWT_COOKIE_SECURE']
        assert not installation.application.config.get('REMOTE_ORIGIN')
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
        post('/inventory/transfers', {'product_id':product['id'],'quantity':'1','unit':'pack','reason':'Allocate retail smoke'})
        retail = post('/sales', {'lines':[{'product_id':product['id'],'quantity':'1','mode':'retail'}],
            'payments':[{'method':'external_mobile','amount':'10','reference':'SMOKE-MPESA-1'}]})
        assert retail['served_by'] == 'installer-test' and retail['transaction_type'] == 'retail'
        assert client.get('/api/register').json['expected_mpesa'] == '10.00'
        supplier = post('/suppliers', {'name':'Installer supplier'})
        draft = post('/purchases', {'supplier_id':supplier['id'],'status':'draft','lines':[{'product_id':product['id'],'quantity':'1','purchase_unit':'pack','unit_cost':'60'}]})
        csrf = {'Idempotency-Key':secrets.token_hex(16),'X-CSRF-TOKEN':client.get_cookie('csrf_access_token').value}
        assert client.put('/api/suppliers/'+str(supplier['id']),json={'name':'Updated supplier'},headers=csrf).status_code == 200
        assert client.put('/api/purchases/'+str(draft['id']),json={'supplier_id':supplier['id'],'status':'ordered','lines':[{'product_id':product['id'],'quantity':'2','purchase_unit':'pack','unit_cost':'60'}]},headers={**csrf,'Idempotency-Key':secrets.token_hex(16)}).status_code == 200
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
            'stock allocations and retail checkout', 'M-Pesa reconciliation', 'supplier edit and draft confirmation', 'restricted runtime database permissions', 'separate remote listener with secure cookies']}), encoding='utf-8')
    finally:
        installation.stop()
