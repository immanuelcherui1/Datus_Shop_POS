import os
import secrets
import sys
from pathlib import Path
import pytest
from sqlalchemy import select, event
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datus import create_app
from datus.extensions import db
from datus.models import Branch, User
from flask_migrate import upgrade


@pytest.fixture()
def app(tmp_path):
    url = os.getenv('TEST_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'test.db'))
    # PostgreSQL tests require a disposable database. No production URI is accepted implicitly.
    if os.getenv('TEST_DATABASE_URL') and 'test' not in url.rsplit('/', 1)[-1]:
        raise RuntimeError('TEST_DATABASE_URL must target a database whose name contains test.')
    application = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': url,
        'SECRET_KEY': secrets.token_hex(32), 'JWT_SECRET_KEY': secrets.token_hex(32),
        'JWT_COOKIE_CSRF_PROTECT': False, 'RATELIMIT_ENABLED': False})
    with application.app_context():
        if db.engine.dialect.name == 'postgresql':
            # Drop only the explicitly disposable test database schema, never any other database.
            with db.engine.begin() as connection:
                connection.exec_driver_sql('DROP SCHEMA public CASCADE')
                connection.exec_driver_sql('CREATE SCHEMA public')
        upgrade()
        branch = Branch(name='Test shop')
        other = Branch(name='Other branch')
        db.session.add_all([branch, other]); db.session.flush()
        password = generate_password_hash('test-only-password')
        db.session.add_all([User(username='owner', password_hash=password, role='owner', branch_id=branch.id),
            User(username='cashier', password_hash=password, role='cashier', branch_id=branch.id),
            User(username='other', password_hash=password, role='owner', branch_id=other.id)])
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    c = app.test_client()
    assert c.post('/api/auth/login', json={'username': 'owner', 'password': 'test-only-password'}).status_code == 200
    return c


def post(client, path, data, key=None):
    return client.post('/api' + path, json=data, headers={'Idempotency-Key': key or secrets.token_hex(16)})


def product(client, sku='RICE'):
    r = post(client, '/products', {'sku': sku, 'name': 'Rice', 'retail_price': '10.00',
        'wholesale_price': '110.00', 'pack_size': '12', 'tax_rate': '0.16'})
    assert r.status_code == 200, r.json
    return r.json


def stock(client, quantity='30'):
    p = product(client)
    r = post(client, '/inventory/adjustments', {'product_id': p['id'], 'quantity': quantity, 'unit_cost': '5', 'reason': 'Opening balance'})
    assert r.status_code == 200, r.json
    assert post(client, '/register/open', {'opening': '100'}).status_code == 200
    return p


def sale_body(product_id=1, quantity='1', payments=None):
    return {'lines': [{'product_id': product_id, 'quantity': quantity, 'mode': 'retail'}],
        'payments': payments or [{'method': 'cash', 'amount': str(__import__('decimal').Decimal(quantity) * __import__('decimal').Decimal('11.60'))}]}
