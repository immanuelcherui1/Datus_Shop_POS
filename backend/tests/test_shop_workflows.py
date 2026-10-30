"""Regression coverage for the shop's pack/unit workflow and account controls."""
import secrets
from decimal import Decimal as D
import pytest
from sqlalchemy import select
from conftest import post, product
from datus.extensions import db
from datus.models import Audit, Stock

@pytest.mark.parametrize('channel,modes', [('wholesale',['wholesale','wholesale_unit']),('retail',['retail_pack','retail'])])
def test_pack_and_unit_share_stock(client, app, channel, modes):
    p=post(client,'/products',{'sku':'SUGAR','name':'Sugar','retail_price':'150','wholesale_price':'7500','pack_size':'50','reorder_packs':'2'}).json
    row=client.get('/api/products').json['items'][0]
    assert D(row['reorder_level'])==100 and D(row['reorder_packs'])==2
    opening={'product_id':p['id'],'quantity':'51','unit_cost':'100','reason':'Opening sugar','location':channel,'password':'test-only-password'}
    assert post(client,'/inventory/adjustments',opening).status_code==200
    assert post(client,'/register/open',{'opening':'0'}).status_code==200
    lines=[{'product_id':p['id'],'quantity':'1','mode':m} for m in modes]
    assert post(client,'/sales/quote',{'lines':[lines[0],lines[0]]}).status_code==400
    too_many={'lines':[lines[0],{**lines[1],'quantity':'2'}],'payments':[{'method':'cash','amount':'7800'}]}
    assert post(client,'/sales',too_many).status_code==409
    body={'lines':lines,'payments':[{'method':'cash','amount':'7650'}]}
    sale=post(client,'/sales',body,'pack-unit-retry');assert sale.status_code==200,sale.json
    assert D(sale.json['total'])==7650 and len(sale.json['lines'])==2
    assert post(client,'/sales',body,'pack-unit-retry').json==sale.json
    with app.app_context():
        s=db.session.scalar(select(Stock).where(Stock.product_id==p['id']))
        assert s.quantity==0 and s.value==0 and s.retail_value==0
    assert client.get('/api/inventory/reconciliation').json['ok']


def test_adjustment_password_and_pack_conversion(client,app):
    p=product(client)
    body={'product_id':p['id'],'quantity':'2','unit':'pack','unit_cost':'5','reason':'Counted two packs'}
    assert post(client,'/inventory/adjustments',body).status_code==403
    assert post(client,'/inventory/adjustments',{**body,'password':'wrong-password'}).status_code==403
    good={**body,'password':'test-only-password'}
    r=post(client,'/inventory/adjustments',good,'pack-adjust-retry');assert r.status_code==200,r.json
    assert D(r.json['quantity'])==24 and D(r.json['value'])==120
    assert post(client,'/inventory/adjustments',{**good,'password':'wrong-password'},'pack-adjust-retry').status_code==403
    assert post(client,'/inventory/adjustments',good,'pack-adjust-retry').json==r.json
    r=post(client,'/inventory/adjustments',{**good,'quantity':'-1'})
    assert D(r.json['quantity'])==12 and D(r.json['value'])==60
    with app.app_context():
        audit=db.session.scalar(select(Audit).where(Audit.action=='stock.adjusted'))
        assert 'password' not in audit.details and D(audit.details['entered_quantity'])==2


def test_owner_updates_and_removes_access(client,app):
    staff=app.test_client()
    assert staff.post('/api/auth/login',json={'username':'cashier','password':'test-only-password'}).status_code==200
    data={'username':'new-cashier','password':'changed-test-password','role':'inventory','active':True}
    def put(c,uid,body):
        return c.put(f'/api/users/{uid}',json=body,headers={'Idempotency-Key':secrets.token_hex(16)})
    assert put(staff,2,data).status_code==403
    assert put(client,2,data).status_code==200
    assert staff.get('/api/auth/me').status_code==401
    assert staff.post('/api/auth/login',json={'username':'new-cashier','password':'test-only-password'}).status_code==401
    assert staff.post('/api/auth/login',json={'username':'new-cashier','password':'changed-test-password'}).status_code==200
    assert put(client,2,{**data,'password':None,'active':False}).status_code==200
    assert staff.post('/api/auth/login',json={'username':'new-cashier','password':'changed-test-password'}).status_code==401
    assert put(client,1,{**data,'username':'owner','active':False}).status_code==400
    assert put(client,3,data).status_code==404
    users=client.get('/api/users').json
    assert any(u['id']==2 and not u['active'] for u in users)
