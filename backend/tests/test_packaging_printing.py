from copy import deepcopy
from decimal import Decimal
import pytest
from conftest import post, stock, sale_body
from datus import printing


def candle_data():
    return dict(sku='CANDLE', name='Candles', unit='piece', packaging_unit='carton', pack_size='96',
        wholesale_price='768', retail_price='10', reorder_packs='2', packages=[
            dict(key='unit', name='piece', conversion='1', wholesale_price=None, retail_price='10'),
            dict(key='packet', name='packet', conversion='8', wholesale_price='64', retail_price='80'),
            dict(key='pack', name='carton', conversion='96', wholesale_price='768', retail_price=None)])


def candles(client):
    r = post(client, '/products', candle_data())
    assert r.status_code == 200, r.json
    pid = r.json['id']
    r = post(client, '/inventory/adjustments', dict(product_id=pid, password='test-only-password',
        packaging_key='pack', quantity='10', unit_cost='5', reason='Opening candles'))
    assert r.status_code == 200, r.json
    return pid


def line(pid, key, qty, mode):
    return dict(product_id=pid, packaging_key=key, quantity=qty, mode=mode)


def test_candle_carton_packet_piece_stock_sales_returns(client):
    pid = candles(client)
    assert post(client, '/register/open', {'opening':'100'}).status_code == 200
    rows = [line(pid,'pack','2','wholesale'), line(pid,'packet','3','wholesale')]
    quote = post(client, '/sales/quote', {'lines':rows})
    assert quote.status_code == 200, quote.json
    assert Decimal(quote.json['total']) == 1728
    assert [Decimal(x['base_quantity']) for x in quote.json['lines']] == [192,24]
    result = post(client, '/sales', {'lines':rows,'payments':[{'method':'cash','amount':'1728'}]}, 'candle-sale-1')
    assert result.status_code == 200, result.json
    assert Decimal(client.get('/api/products').json['items'][0]['quantity']) == 744
    assert post(client, '/inventory/transfers', dict(product_id=pid,packaging_key='pack',quantity='1',reason='Retail candles')).status_code == 200
    retail = post(client, '/sales', {'lines':[line(pid,'packet','1','retail_pack'),line(pid,'unit','3','retail')], 'payments':[{'method':'cash','amount':'110'}]})
    assert retail.status_code == 200, retail.json
    assert [Decimal(x['base_quantity']) for x in retail.json['lines']] == [8,3]
    p = client.get('/api/products').json['items'][0]
    assert Decimal(p['quantity']) == 733 and Decimal(p['retail_quantity']) == 85
    assert Decimal(p['reorder_level']) == 192
    returned = post(client, f"/sales/{retail.json['id']}/returns", dict(reason='Customer returned packet',
        lines=[dict(line_id=retail.json['lines'][0]['id'],quantity='1',disposition='restock')],
        refunds=[dict(payment_id=retail.json['payments'][0]['id'],amount='80')]))
    assert returned.status_code == 200, returned.json
    p = client.get('/api/products').json['items'][0]
    assert Decimal(p['quantity']) == 741 and Decimal(p['retail_quantity']) == 93
    assert client.get('/api/inventory/reconciliation').json['ok']


@pytest.mark.parametrize('rows', [
    [('unit','1','wholesale_unit')], [('pack','1','retail_pack')],
    [('packet','0.5','retail')], [('packet','1','wholesale'),('packet','1','wholesale')],
    [('missing','1','wholesale')], [('packet','1','wholesale'),('unit','1','retail')],
])
def test_invalid_or_disabled_packaging_rejected(client,rows):
    pid = candles(client)
    result = post(client, '/sales/quote', {'lines':[line(pid,*r) for r in rows]})
    assert result.status_code == 400, result.json
    assert Decimal(client.get('/api/products').json['items'][0]['quantity']) == 960


def test_packaging_factors_locked_prices_editable_and_purchase_snapshots(client):
    pid = candles(client)
    supplier = post(client, '/suppliers', {'name':'Candles supplier'}).json['id']
    order = post(client, '/purchases', dict(supplier_id=supplier,lines=[dict(product_id=pid,packaging_key='pack',purchase_unit='pack',quantity='2',unit_cost='600')]))
    assert order.status_code == 200, order.json
    assert Decimal(order.json['total']) == 1200
    data = candle_data();data['packages'][1]['conversion']='9'
    assert client.put(f'/api/products/{pid}',json=data,headers={'Idempotency-Key':'change-factor'}).status_code == 409
    data=candle_data();data['packages'][1]['wholesale_price']='70'
    assert client.put(f'/api/products/{pid}',json=data,headers={'Idempotency-Key':'change-price'}).status_code == 200
    receipt = post(client, f"/purchases/{order.json['id']}/receipts", {'lines':[dict(line_id=order.json['lines'][0]['id'],packaging_key='packet',quantity='12')]})
    assert receipt.status_code == 200, receipt.json
    p = client.get('/api/products').json['items'][0]
    assert Decimal(p['quantity']) == 1056 and Decimal(p['inventory_value']) == 5400
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_combined_packaging_oversell_rolls_back(client):
    pid=candles(client)
    assert post(client,'/register/open',{'opening':'0'}).status_code==200
    r=post(client,'/sales',dict(lines=[line(pid,'pack','10','wholesale'),line(pid,'packet','1','wholesale')],payments=[dict(method='cash',amount='7744')]))
    assert r.status_code==409
    assert Decimal(client.get('/api/products').json['items'][0]['quantity'])==960
    assert not client.get('/api/sales').json['items']


def posted_sale(client):
    p=stock(client)
    result=post(client,'/sales',sale_body(p['id']))
    assert result.status_code==200,result.json
    return result.json


def test_text_receipt_width_controls_amounts_and_escape_injection(client):
    sale=posted_sale(client)
    sale['lines'][0]['name']='Candles\x1b@\n'+'Very long item '*8
    raw=printing.receipt_bytes(sale,32,'text',True)
    assert b'\x1b' not in raw and b'\x1d' not in raw
    assert all(len(row)<=32 for row in raw.split(b'\r\n'))
    assert b'11.60' in raw and b'Cash retained' in raw
    raw=printing.receipt_bytes(sale,48,'escpos',True)
    assert raw.startswith(b'\x1b@') and raw.endswith(b'\x1dV\x00')


def test_print_retry_does_not_resend_or_mutate_sale(client,monkeypatch):
    sale=posted_sale(client);calls=[]
    monkeypatch.setattr(printing,'printers',lambda:['XP-80S'])
    monkeypatch.setattr(printing,'send_raw',lambda *args: calls.append(args) or 42)
    data=dict(printer='XP-80S',columns=48,mode='text',cut=False)
    path=f"/sales/{sale['id']}/print"
    a=post(client,path,data,'receipt-print-1');b=post(client,path,data,'receipt-print-1')
    assert a.status_code==200 and a.json==b.json and a.json['status']=='queued'
    assert len(calls)==1
    assert client.get(f"/api/sales/{sale['id']}").json['total']==sale['total']
    assert post(client,path,{**data,'columns':32},'receipt-print-1').status_code==409
    assert post(client,path,{**data,'printer':'arbitrary remote host'}).status_code==400


def test_uncertain_print_requires_explicit_new_copy(client,monkeypatch):
    sale=posted_sale(client);calls=[]
    monkeypatch.setattr(printing,'printers',lambda:['XP-80S'])
    def fail(*args):
        calls.append(args);raise OSError('Lost after partial write')
    monkeypatch.setattr(printing,'send_raw',fail)
    data=dict(printer='XP-80S')
    path=f"/sales/{sale['id']}/print"
    assert post(client,path,data,'uncertain-copy').json['status']=='unknown'
    assert post(client,path,data,'uncertain-copy').json['status']=='unknown'
    assert len(calls)==1
    assert post(client,path,data,'explicit-copy').json['status']=='unknown'
    assert len(calls)==2


def test_print_is_branch_scoped_and_test_is_not_sale(client,monkeypatch):
    sale=posted_sale(client)
    monkeypatch.setattr(printing,'printers',lambda:['XP-80S'])
    monkeypatch.setattr(printing,'send_raw',lambda *args:1)
    assert post(client,'/printing/test',dict(printer='XP-80S')).json['status']=='queued'
    assert len(client.get('/api/sales').json['items'])==1
    client.post('/api/auth/login',json=dict(username='other',password='test-only-password'))
    assert post(client,f"/sales/{sale['id']}/print",dict(printer='XP-80S')).status_code==404
