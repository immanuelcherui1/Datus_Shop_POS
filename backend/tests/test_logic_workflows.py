"""End-to-end invariants across purchase, stock, settlement and correction workflows."""
from decimal import Decimal as D
import secrets
import pytest
from sqlalchemy import select, text, func
from conftest import post
from datus.extensions import db
from datus.models import Stock, CashMovement, Purchase, Movement

PASSWORD='test-only-password'

def item(client,pack='3',sku='FLOW'):
    data={'sku':sku,'name':'Workflow item','unit':'kg','packaging_unit':'bag','pack_size':pack,'retail_price':'10','wholesale_price':'30'}
    r=post(client,'/products',data);assert r.status_code==200,r.json
    return r.json,data

def order(client,p,quantity='3',cost='10',unit='pack',status='ordered'):
    supplier=post(client,'/suppliers',{'name':'Supplier '+secrets.token_hex(4)}).json
    r=post(client,'/purchases',{'supplier_id':supplier['id'],'status':status,'lines':[{'product_id':p['id'],'quantity':quantity,'unit_cost':cost,'purchase_unit':unit}]})
    assert r.status_code==200,r.json
    return r.json

def receive(client,o,qty,unit='unit',cost=None,key=None):
    return post(client,f"/purchases/{o['id']}/receipts",{'lines':[{'line_id':o['lines'][0]['id'],'quantity':qty,'unit':unit,'unit_cost':cost}]},key)

def purchase(client,oid):
    return next(x for x in client.get('/api/purchases').json['items'] if x['id']==oid)

def open_till(client,cash='1000',mpesa='1000'):
    r=post(client,'/register/open',{'opening':cash,'opening_mpesa':mpesa});assert r.status_code==200,r.json

def funds(client,amount='10',kind='cash_out',method='cash',reference=None,key=None):
    return post(client,'/register/movements',{'kind':kind,'amount':amount,'method':method,'reference':reference,'reason':'Recorded test movement'},key)

def pay(client,o,amount='10',method='cash',reference=None,key=None):
    return post(client,f"/purchases/{o['id']}/payments",{'amount':amount,'method':method,'reference':reference,'reason':'Verified supplier payment'},key)

def reverse(client,entry,reference=None,key=None):
    return post(client,f"/register/movements/{entry['id']}/reversal",{'reason':'Money actually returned','reference':reference},key)


def test_exact_pack_order_and_partial_receipts(client,app):
    p,_=item(client)
    o=order(client,p,'10000','1')
    assert D(o['total'])==10000 and D(o['lines'][0]['line_total'])==10000
    assert receive(client,o,'1',key='first-receipt').status_code==200
    assert receive(client,o,'1',key='first-receipt').status_code==200
    assert receive(client,o,'1').status_code==200
    assert receive(client,o,'29998').status_code==200
    with app.app_context():
        stock=db.session.get(Stock,(p['id'],1))
        assert stock.quantity==30000 and stock.value==10000
    assert D(purchase(client,o['id'])['received_value'])==10000
    assert receive(client,o,'1').status_code==409
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_receiving_units_and_actual_cost_override(client):
    p,_=item(client,'50');o=order(client,p,'100','2',unit='unit')
    r=receive(client,o,'1','pack','125');assert r.status_code==200,r.json
    r=receive(client,o,'50','unit','3');assert r.status_code==200,r.json
    row=client.get('/api/products').json['items'][0]
    assert D(row['quantity'])==100 and D(row['inventory_value'])==275
    o=purchase(client,o['id']);assert D(o['total'])==200 and D(o['received_value'])==275
    assert o['status']=='received'


def test_sell_out_retains_cost_and_forbids_unit_reinterpretation(client):
    p,data=item(client,'3');o=order(client,p,'1','1');assert receive(client,o,'1','pack').status_code==200
    open_till(client)
    assert post(client,'/sales',{'lines':[{'product_id':p['id'],'quantity':'1','mode':'wholesale'}],'payments':[{'method':'cash','amount':'30'}]}).status_code==200
    row=client.get('/api/products').json['items'][0]
    assert D(row['quantity'])==0 and D(row['cost_per_unit'])==D('.333333') and D(row['cost_per_pack'])==1
    for changes in ({'unit':'g'},{'pack_size':'6'}):
        r=client.put(f"/api/products/{p['id']}",json={**data,**changes},headers={'Idempotency-Key':secrets.token_hex(16)})
        assert r.status_code==409,r.json
    r=client.put(f"/api/products/{p['id']}",json={**data,'name':'Renamed'},headers={'Idempotency-Key':secrets.token_hex(16)})
    assert r.status_code==200,r.json


def test_unused_units_editable_but_draft_locks_conversion(client):
    p,data=item(client)
    update=lambda x:client.put(f"/api/products/{p['id']}",json={**data,**x},headers={'Idempotency-Key':secrets.token_hex(16)})
    assert update({'pack_size':'6'}).status_code==200
    o=order(client,p,status='draft')
    assert update({'pack_size':'3'}).status_code==409
    assert receive(client,o,'1').status_code==409
    assert D(client.get('/api/products').json['items'][0]['quantity'])==0


def test_reverse_allocation_conserves_quantity_value_and_retries(client,app):
    p,_=item(client)
    assert post(client,'/inventory/adjustments',{'product_id':p['id'],'quantity':'3','unit_cost':'0.333333','reason':'Opening balance','password':PASSWORD}).status_code==200
    body={'product_id':p['id'],'quantity':'1','unit':'pack','reason':'Shelf allocation'}
    assert post(client,'/inventory/transfers',body).status_code==200
    back={**body,'source':'retail'}
    r=post(client,'/inventory/transfers',back,'reverse-allocation');assert r.status_code==200,r.json
    assert post(client,'/inventory/transfers',back,'reverse-allocation').json==r.json
    assert post(client,'/inventory/transfers',back).status_code==409
    with app.app_context():
        s=db.session.get(Stock,(p['id'],1));assert s.quantity==3 and s.value==D('.999999') and s.retail_quantity==0 and s.retail_value==0
        legs=db.session.scalars(select(Movement).where(Movement.transfer_reference==r.json['reference'])).all()
        assert len(legs)==2 and sum(x.quantity for x in legs)==0 and sum(x.value for x in legs)==0
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_supplier_payments_actual_value_reversal_and_close(client,app):
    p,_=item(client);o=order(client,p,'1','10');open_till(client,'20','20')
    assert pay(client,o).status_code==409 # Not received, no payable.
    assert receive(client,o,'1','pack','12').status_code==200
    r=pay(client,o,'7',key='supplier-retry');assert r.status_code==200,r.json
    assert pay(client,o,'7',key='supplier-retry').json==r.json
    assert pay(client,o,'6').status_code==409
    assert pay(client,o,'5','external_mobile').status_code==400
    m=pay(client,o,'5','external_mobile','MPESA-SUPPLIER');assert m.status_code==200,m.json
    assert D(purchase(client,o['id'])['outstanding'])==0
    assert D(client.get('/api/register').json['expected'])==13
    assert D(client.get('/api/register').json['expected_mpesa'])==15
    rev=reverse(client,r.json,key='reverse-supplier');assert rev.status_code==200,rev.json
    assert reverse(client,r.json,key='reverse-supplier').json==rev.json
    assert reverse(client,r.json).status_code==409
    assert D(purchase(client,o['id'])['outstanding'])==7
    assert pay(client,o,'7','external_bank','BANK-SUPPLIER').status_code==200
    close=post(client,'/register/close',{'counted':'20','counted_mpesa':'15'});assert close.status_code==200,close.json
    assert pay(client,o,'1').status_code==409
    with app.app_context():
        with pytest.raises(Exception):db.session.execute(text('DELETE FROM cash_movement'))
        db.session.rollback()


def test_cash_movements_enforce_balance_and_retry(client):
    assert funds(client).status_code==409
    open_till(client,'0','0')
    assert funds(client).status_code==409
    incoming=funds(client,'20','cash_in',key='cash-in-retry');assert incoming.status_code==200
    assert funds(client,'20','cash_in',key='cash-in-retry').json==incoming.json
    outgoing=funds(client,'15');assert outgoing.status_code==200
    assert reverse(client,incoming.json).status_code==409 # Cannot undo money already spent.
    assert reverse(client,outgoing.json).status_code==200
    assert reverse(client,incoming.json).status_code==200
    assert D(client.get('/api/register').json['expected'])==0
    assert funds(client,'1','cash_in','external_bank','BANK').status_code==400
    assert funds(client,'1','cash_in','external_mobile','MONEY-1').status_code==200
    assert funds(client,'1','cash_in','external_mobile','MONEY-1').status_code==409


def test_permissions_scope_and_historical_purchase_status(client,app):
    p,_=item(client);o=order(client,p);assert receive(client,o,'1','pack').status_code==200
    open_till(client)
    cashier=app.test_client();cashier.post('/api/auth/login',json={'username':'cashier','password':PASSWORD})
    other=app.test_client();other.post('/api/auth/login',json={'username':'other','password':PASSWORD})
    open_till(other)
    assert pay(cashier,o).status_code==403 and funds(cashier).status_code==403
    assert pay(other,o).status_code==404
    assert post(other,'/sales/quote',{'lines':[{'product_id':p['id'],'quantity':'1','mode':'retail'}]}).status_code==400
    with app.app_context():
        db.session.get(Purchase,o['id']).payments_tracked=False;db.session.commit()
    assert pay(client,o).status_code==409


def test_refund_needs_actual_funds_in_current_session(client):
    p,_=item(client);o=order(client,p,'1','1');receive(client,o,'1','pack');open_till(client,'0','0')
    sale=post(client,'/sales',{'lines':[{'product_id':p['id'],'quantity':'1','mode':'wholesale'}],'payments':[{'method':'cash','amount':'30'}]}).json
    assert post(client,'/register/close',{'counted':'30','counted_mpesa':'0'}).status_code==200
    open_till(client,'0','0')
    refund={'reason':'Customer return','lines':[{'line_id':sale['lines'][0]['id'],'quantity':'1','disposition':'restock'}],'refunds':[{'payment_id':sale['payments'][0]['id'],'amount':'30'}]}
    assert post(client,f"/sales/{sale['id']}/returns",refund).status_code==409
    assert funds(client,'30','cash_in').status_code==200
    assert post(client,f"/sales/{sale['id']}/returns",refund).status_code==200
    assert D(client.get('/api/register').json['expected'])==0
