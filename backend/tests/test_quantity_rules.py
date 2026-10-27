from decimal import Decimal
import pytest
from marshmallow import ValidationError
from datus.schemas import ProductSchema, PurchaseLineSchema, ReceiveLineSchema, AdjustmentSchema, CartLineSchema
from conftest import post, stock, sale_body


@pytest.mark.parametrize('schema,payload', [
    (ProductSchema, dict(sku='A', name='Item', retail_price='1.25', wholesale_price='12.50', pack_size='1.5')),
    (ProductSchema, dict(sku='A', name='Item', retail_price='1.25', wholesale_price='12.50', pack_size='12', reorder_level='0.5')),
    (PurchaseLineSchema, dict(product_id=1, quantity='1.5', unit_cost='0.123456')),
    (ReceiveLineSchema, dict(line_id=1, quantity='0.5')),
    (AdjustmentSchema, dict(product_id=1, quantity='-0.5', reason='Stock count')),
    (CartLineSchema, dict(product_id=1, quantity='1.5', mode='wholesale')),
])
def test_fractional_nonretail_input_is_rejected(schema, payload):
    with pytest.raises(ValidationError):
        schema().load(payload)


def test_retail_fraction_and_whole_padded_quantity():
    assert CartLineSchema().load(dict(product_id=1, quantity='0.125', mode='retail'))['quantity'] == Decimal('0.125')
    assert CartLineSchema().load(dict(product_id=1, quantity='2.000', mode='wholesale'))['quantity'] == Decimal('2')


def test_fractional_retail_sale_preserves_stock_and_wholesale_rejects(client):
    p = stock(client)
    sale = post(client, '/sales', sale_body(p['id'], '0.5'))
    assert sale.status_code == 200, sale.json
    assert client.get('/api/products').json['items'][0]['quantity'] == '29.500'
    body = sale_body(p['id'], '0.5')
    body['lines'][0]['mode'] = 'wholesale'
    assert post(client, '/sales/quote', {'lines': body['lines']}).status_code == 400
    assert post(client, '/sales', body).status_code == 400
    assert client.get('/api/inventory/reconciliation').json['ok']



def test_wholesale_return_requires_whole_packs(client):
    p = stock(client)
    body = {'lines': [{'product_id': p['id'], 'quantity': '1', 'mode': 'wholesale'}],
            'payments': [{'method': 'cash', 'amount': '127.60'}]}
    sale = post(client, '/sales', body).json
    payload = {'reason': 'Customer return', 'lines': [{'line_id': sale['lines'][0]['id'], 'quantity': '0.5', 'disposition': 'restock'}],
               'refunds': [{'payment_id': sale['payments'][0]['id'], 'amount': '63.80'}]}
    assert post(client, f"/sales/{sale['id']}/returns", payload).status_code == 400
    payload['lines'][0]['quantity'] = '1'
    payload['refunds'][0]['amount'] = '127.60'
    assert post(client, f"/sales/{sale['id']}/returns", payload).status_code == 200
    assert client.get('/api/products').json['items'][0]['quantity'] == '30.000'
