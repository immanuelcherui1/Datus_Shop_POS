"""These guarantees must run against PostgreSQL; SQLite cannot prove row locking."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from datus.extensions import db
from conftest import post, stock, sale_body


@pytest.mark.postgres
@pytest.mark.parametrize('same_key', [False, True])
def test_parallel_checkout_does_not_oversell(app, client, same_key):
    with app.app_context():
        if db.engine.dialect.name != 'postgresql':
            pytest.skip('Set TEST_DATABASE_URL to a disposable PostgreSQL database.')
    stock(client, '1')
    barrier = Barrier(2)
    def worker(index):
        c = app.test_client()
        c.post('/api/auth/login', json={'username': 'owner', 'password': 'test-only-password'})
        barrier.wait(timeout=10)
        key = 'same-checkout-key' if same_key else f'checkout-key-{index}'
        return post(c, '/sales', sale_body(), key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))
    assert all(r.status_code in (200, 409) for r in results), [(r.status_code, r.json) for r in results]
    assert any(r.status_code == 200 for r in results)
    assert client.get('/api/sales').json['total'] == 1
    assert client.get('/api/products').json['items'][0]['quantity'] == '0.000'
    assert client.get('/api/inventory/reconciliation').json['ok']
    if same_key:
        assert all(r.status_code == 200 for r in results)
        assert post(client, '/sales', sale_body(), 'same-checkout-key').status_code == 200
