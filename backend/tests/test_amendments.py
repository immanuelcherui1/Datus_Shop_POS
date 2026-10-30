"""Cross-module acceptance: allocations, four prices, receipts and settlement accountability."""
from decimal import Decimal as D
from sqlalchemy import select, func, text
from conftest import post, product, sale_body
from datus.extensions import db
from datus.models import Stock, Movement, Sale, Payment, CashMovement, Audit


def seed(client, qty='60'):
    p=product(client)
    assert post(client,'/inventory/adjustments',{'password':'test-only-password','product_id':p['id'],'quantity':qty,'unit_cost':'5','reason':'Opening wholesale'}).status_code==200
    assert post(client,'/register/open',{'opening':'100','opening_mpesa':'200'}).status_code==200
    return p


def allocate(client,p,qty='2',unit='pack',key=None):
    return post(client,'/inventory/transfers',{'product_id':p['id'],'quantity':qty,'unit':unit,'reason':'Allocate retail stock'},key)


def test_transfer_conserves_stock_value_and_retry(client,app):
    p=seed(client)
    first=allocate(client,p,key='allocation-retry-1');assert first.status_code==200,first.json
    assert allocate(client,p,key='allocation-retry-1').json==first.json
    data=client.get('/api/products').json['items'][0]
    assert D(data['quantity'])==60 and D(data['inventory_value'])==300
    assert D(data['wholesale_quantity'])==36 and D(data['retail_quantity'])==24
    with app.app_context():
        legs=db.session.scalars(select(Movement).where(Movement.transfer_reference==first.json['reference'])).all()
        assert len(legs)==2 and sum(x.quantity for x in legs)==0 and sum(x.value for x in legs)==0
        assert all(x.user_id==1 for x in legs)
    assert allocate(client,p,'37','unit').status_code==409
    assert client.get('/api/inventory/reconciliation').json['ok']
    cashier=app.test_client();cashier.post('/api/auth/login',json={'username':'cashier','password':'test-only-password'})
    assert allocate(cashier,p).status_code==403


def test_all_four_modes_and_channel_isolation(client):
    p=seed(client,'100')
    assert post(client,'/sales',sale_body(p['id'])).status_code==409
    assert allocate(client,p,'4').status_code==200
    for mode,qty,expected,base in [('wholesale','1','127.60','12'),('wholesale_unit','3','31.90','3'),('retail','0.5','5.80','0.5'),('retail_pack','1','139.20','12')]:
        body={'lines':[{'product_id':p['id'],'mode':mode,'quantity':qty}]}
        quote=post(client,'/sales/quote',body);assert quote.status_code==200,quote.json
        assert D(quote.json['total'])==D(expected)
        body['payments']=[{'method':'cash','amount':expected}]
        sale=post(client,'/sales',body);assert sale.status_code==200,sale.json
        assert D(sale.json['lines'][0]['base_quantity'])==D(base)
        assert sale.json['served_by']=='owner'
    rows=client.get('/api/products').json['items'][0]
    assert D(rows['quantity'])==D('72.5') and D(rows['retail_quantity'])==D('35.5')
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_split_mpesa_refund_and_session_accountability(client):
    p=seed(client);allocate(client,p)
    payload=sale_body(p['id'],payments=[{'method':'cash','amount':'6.60'},{'method':'external_mobile','amount':'5','reference':'MPESA-NEW-1'}])
    sale=post(client,'/sales',payload).json
    session=client.get('/api/register').json
    assert D(session['expected'])==D('106.60') and D(session['expected_mpesa'])==205
    refund={'reason':'Customer returned goods','lines':[{'line_id':sale['lines'][0]['id'],'quantity':'1','disposition':'restock'}],
      'refunds':[{'payment_id':sale['payments'][0]['id'],'amount':'6.60'},{'payment_id':sale['payments'][1]['id'],'amount':'5','reference':'MPESA-REFUND-1'}]}
    assert post(client,f"/sales/{sale['id']}/returns",refund).status_code==200
    session=client.get('/api/register').json
    assert D(session['expected'])==100 and D(session['expected_mpesa'])==200
    assert post(client,'/register/close',{'counted':'100','counted_mpesa':'199'}).status_code==400
    closed=post(client,'/register/close',{'counted':'100','counted_mpesa':'199','notes':'Declared shortage reviewed'}).json
    assert closed['closed_by']=='owner' and D(closed['variance_mpesa'])==-1
    assert client.get('/api/register/history').json['items'][0]['notes']=='Declared shortage reviewed'
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_draft_purchase_pack_cost_actual_receiving_and_supplier(client):
    p=product(client)
    supplier=post(client,'/suppliers',{'name':'Vendor One','email':'v@example.com','address':'Nairobi'}).json
    assert post(client,'/suppliers',{'name':' vendor one '}).status_code==409
    data={'supplier_id':supplier['id'],'status':'draft','lines':[{'product_id':p['id'],'quantity':'5','purchase_unit':'pack','unit_cost':'1200'}]}
    draft=post(client,'/purchases',data);assert draft.status_code==200,draft.json
    line=draft.json['lines'][0]
    assert D(line['quantity'])==60 and D(line['unit_cost'])==100
    assert D(draft.json['total'])==6000
    assert post(client,f"/purchases/{draft.json['id']}/receipts",{'lines':[{'line_id':line['id'],'quantity':'12'}]}).status_code==409
    data['lines'][0]['quantity']='2';data['status']='ordered'
    confirmed=client.put(f"/api/purchases/{draft.json['id']}",json=data,headers={'Idempotency-Key':'confirm-order-1'})
    assert confirmed.status_code==200,confirmed.json
    assert D(client.get('/api/products').json['items'][0]['quantity'])==0
    line=confirmed.json['lines'][0]
    receipt=post(client,f"/purchases/{draft.json['id']}/receipts",{'lines':[{'line_id':line['id'],'quantity':'12','unit_cost':'101'}]})
    assert receipt.status_code==200,receipt.json
    stock=client.get('/api/products').json['items'][0]
    assert D(stock['wholesale_quantity'])==12 and D(stock['retail_quantity'])==0 and D(stock['inventory_value'])==1212
    assert client.get('/api/purchases').json['items'][0]['prepared_by']=='owner'
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_filters_insights_catalogue_and_mixed_rejection(client):
    p=seed(client);allocate(client,p)
    sale=post(client,'/sales',sale_body(p['id']));assert sale.status_code==200
    assert len(client.get('/api/sales?type=retail&method=cash&user_id=1').json['items'])==1
    assert client.get('/api/sales?type=wholesale').json['items']==[]
    r=client.get('/api/reports/insights');assert r.status_code==200,r.json
    assert r.json['total_products']==1 and len(r.json['fast'])==1 and D(r.json['payments']['Cash'])==D('11.60')
    assert client.get('/api/reports/insights?start=2026-10-30&end=2026-01-01').status_code==400
    assert any(x['name']=='piece' for x in client.get('/api/catalogue-options').json)
    p2=product(client,'SUGAR')
    assert post(client,'/sales/quote',{'lines':[{'product_id':p['id'],'quantity':'1','mode':'retail'},{'product_id':p2['id'],'quantity':'1','mode':'wholesale'}]}).status_code==400
