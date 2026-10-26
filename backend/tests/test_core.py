from decimal import Decimal
from sqlalchemy import select, func, text
import pytest
from datus.extensions import db
from datus.models import Sale, SaleLine, Payment, Movement, Stock, Audit, Product, Refund
from conftest import post, product, stock, sale_body


def test_product_and_duplicate_sku(client):
    p = product(client)
    assert p['retail_price'] == '10.00'
    assert post(client, '/products', {'sku': 'RICE', 'name': 'Duplicate', 'retail_price': '10', 'wholesale_price': '10', 'pack_size': '1'}).status_code == 409


def test_reject_float_nan_and_unknown_fields(client):
    for invalid in [1.23, 'NaN', 'Infinity', '1.001', '-1']:
        assert post(client, '/products', {'sku': 'X', 'name': 'X', 'retail_price': invalid,
            'wholesale_price': '10', 'pack_size': '1'}).status_code == 400


def test_partial_purchase_receipt_and_retry(client):
    p = product(client)
    supplier = post(client, '/suppliers', {'name': 'Supplier'}).json
    purchase = post(client, '/purchases', {'supplier_id': supplier['id'], 'lines': [
        {'product_id': p['id'], 'quantity': '20', 'unit_cost': '5'}]}).json
    assert client.get('/api/products').json['items'][0]['quantity'] == '0.000'
    body = {'lines': [{'line_id': purchase['lines'][0]['id'], 'quantity': '5'}]}
    r = post(client, f"/purchases/{purchase['id']}/receipts", body, 'receipt-1234')
    assert r.status_code == 200, r.json
    assert post(client, f"/purchases/{purchase['id']}/receipts", body, 'receipt-1234').json == r.json
    assert client.get('/api/products').json['items'][0]['quantity'] == '5.000'
    assert client.get('/api/purchases').json['items'][0]['status'] == 'partial'
    body['lines'][0]['quantity'] = '16'
    assert post(client, f"/purchases/{purchase['id']}/receipts", body).status_code == 409
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_checkout_snapshot_idempotency_and_reconciliation(client):
    p = stock(client)
    body = sale_body(p['id'])
    r = post(client, '/sales', body, 'checkout-1234')
    assert r.status_code == 200, r.json
    assert post(client, '/sales', body, 'checkout-1234').json == r.json
    changed = sale_body(p['id'], '2')
    assert post(client, '/sales', changed, 'checkout-1234').status_code == 409
    assert client.get('/api/products').json['items'][0]['quantity'] == '29.000'
    assert client.get('/api/inventory/reconciliation').json['ok']
    updated = {k: p[k] for k in ['sku', 'name', 'retail_price', 'wholesale_price', 'pack_size', 'tax_rate']}
    updated['retail_price'] = '99'
    response = client.put(f"/api/products/{p['id']}", json=updated, headers={'Idempotency-Key': 'edit-product-123'})
    assert response.status_code == 200, response.json
    historical = client.get(f"/api/sales/{r.json['id']}").json
    assert historical['lines'][0]['unit_price'] == '10.00'
    assert historical['total'] == '11.60'
    assert historical['lines'][0]['cost'] == '5.000000'


def test_rollback_on_stock_failure(client, app):
    stock(client, '1')
    assert post(client, '/sales', sale_body(quantity='2')).status_code == 409
    with app.app_context():
        assert db.session.scalar(select(func.count(Sale.id))) == 0
        assert db.session.scalar(select(func.count(Payment.id))) == 0
        assert db.session.scalar(select(func.count(Movement.id))) == 1
        assert db.session.get(Stock, (1, 1)).quantity == 1


def test_rollback_after_all_critical_steps(client, app):
    stock(client)
    app.config['FAIL_CHECKOUT'] = True
    assert post(client, '/sales', sale_body(), 'fail-key-123').status_code == 500
    with app.app_context():
        assert db.session.scalar(select(func.count(Sale.id))) == 0
        assert db.session.scalar(select(func.count(Payment.id))) == 0
        assert db.session.scalar(select(func.count(Movement.id))) == 1
    app.config['FAIL_CHECKOUT'] = False
    assert post(client, '/sales', sale_body(), 'fail-key-123').status_code == 200


def test_split_payments_cash_reconciliation_and_reference_dedup(client):
    stock(client)
    payments = [{'method': 'cash', 'amount': '6.60'}, {'method': 'external_mobile', 'amount': '5.00', 'reference': 'verified-test-001'}]
    assert post(client, '/sales', sale_body(payments=payments)).status_code == 200
    assert client.get('/api/register').json['expected'] == '106.60'
    assert post(client, '/sales', sale_body(payments=payments)).status_code == 409
    assert client.get('/api/register').json['expected'] == '106.60'
    assert post(client, '/sales', sale_body(payments=[{'method': 'cash', 'amount': '10'}])).status_code == 400
    closed = post(client, '/register/close', {'counted': '106.60'})
    assert closed.status_code == 200, closed.json
    assert closed.json['variance'] == '0.00'


def test_wholesale_pack_consumes_base_units(client):
    stock(client)
    body = {'lines': [{'product_id': 1, 'quantity': '2', 'mode': 'wholesale'}], 'payments': [{'method': 'cash', 'amount': '255.20'}]}
    r = post(client, '/sales', body)
    assert r.status_code == 200, r.json
    assert client.get('/api/products').json['items'][0]['quantity'] == '6.000'
    assert r.json['cost'] == '120.000000'


def test_return_limits_traceability_and_disposition(client, app):
    stock(client)
    sale = post(client, '/sales', sale_body(quantity='2')).json
    payload = {'reason': 'Customer returned item', 'lines': [{'line_id': sale['lines'][0]['id'], 'quantity': '1', 'disposition': 'damaged'}],
        'refunds': [{'payment_id': sale['payments'][0]['id'], 'amount': '11.60'}]}
    r = post(client, f"/sales/{sale['id']}/returns", payload)
    assert r.status_code == 200, r.json
    assert client.get('/api/products').json['items'][0]['quantity'] == '28.000'
    payload['lines'][0]['disposition'] = 'restock'
    assert post(client, f"/sales/{sale['id']}/returns", payload).status_code == 200
    assert post(client, f"/sales/{sale['id']}/returns", payload).status_code == 409
    assert client.get('/api/products').json['items'][0]['quantity'] == '29.000'
    assert client.get('/api/register').json['expected'] == '100.00'
    with app.app_context():
        assert db.session.scalar(select(func.count(Refund.id)).where(Refund.payment_id == sale['payments'][0]['id'])) == 2


def test_immutable_ledger_database_and_orm(client, app):
    stock(client)
    with app.app_context():
        row = db.session.get(Movement, 1)
        row.reason = 'Trying to change history'
        with pytest.raises(ValueError): db.session.commit()
        db.session.rollback()
        for sql in ['DELETE FROM movement WHERE id=1', "UPDATE movement SET reason='changed' WHERE id=1"]:
            with pytest.raises(Exception):
                db.session.execute(text(sql)); db.session.commit()
            db.session.rollback()
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_permissions_and_branch_scope(client, app):
    stock(client)
    sale = post(client, '/sales', sale_body()).json
    other = app.test_client()
    other.post('/api/auth/login', json={'username': 'other', 'password': 'test-only-password'})
    assert other.get(f"/api/sales/{sale['id']}").status_code == 404
    assert other.get('/api/sales').json['items'] == []
    assert post(other, '/sales', sale_body()).status_code == 409
    cashier = app.test_client()
    cashier.post('/api/auth/login', json={'username': 'cashier', 'password': 'test-only-password'})
    assert post(cashier, '/inventory/adjustments', {'product_id': 1, 'quantity': '1', 'reason': 'unauthorized'}).status_code == 403
    assert cashier.get('/api/reports/daily').status_code == 403
    assert post(client, '/inventory/adjustments', {'product_id': 1, 'quantity': '1', 'unit_cost': '5', 'reason': ''}).status_code == 400
    body = sale_body(); body['lines'][0]['discount'] = '1'
    assert post(cashier, '/sales', body).status_code == 403


def test_daily_report(client):
    stock(client)
    assert post(client, '/sales', sale_body()).status_code == 200
    data = client.get('/api/reports/daily').json
    assert data['transactions'] == 1
    assert Decimal(data['sales_including_tax']) == Decimal('11.60')
    assert Decimal(data['gross_profit']) == Decimal('5.00')
    assert Decimal(data['tax']) == Decimal('1.60')


def test_csrf_logout_and_revocation(client, app):
    app.config['JWT_COOKIE_CSRF_PROTECT'] = True
    client.post('/api/auth/login', json={'username': 'owner', 'password': 'test-only-password'})
    assert client.post('/api/auth/logout', json={}).status_code == 401
    csrf = client.get_cookie('csrf_access_token').value
    token = client.get_cookie('access_token_cookie').value
    assert client.post('/api/auth/logout', json={}, headers={'X-CSRF-TOKEN': csrf}).status_code == 200
    client.set_cookie('access_token_cookie', token)
    assert client.get('/api/auth/me').status_code == 401
