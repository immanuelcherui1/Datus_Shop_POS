"""Upgrade a populated previous-version database without changing posted history."""
import secrets
import pytest
from flask_migrate import upgrade
from sqlalchemy import text
from datus import create_app
from datus.extensions import db


def old_app(tmp_path):
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'old.db'),
        'SECRET_KEY':secrets.token_hex(32),'JWT_SECRET_KEY':secrets.token_hex(32)})
    with app.app_context():
        upgrade(revision='0002')
        for sql in [
          "INSERT INTO branch(id,name) VALUES(1,'Legacy shop')",
          "INSERT INTO user(id,username,password_hash,role,branch_id,active,token_version) VALUES(1,'owner','test-hash','owner',1,1,1)",
          "INSERT INTO product(id,sku,name,category,unit,retail_price,wholesale_price,pack_size,tax_rate,reorder_level,active) VALUES(1,'OLD','Old item','Food','bottle',10,110,12,0,5,1)",
          "INSERT INTO stock(product_id,branch_id,quantity,value) VALUES(1,1,24,120)",
          "INSERT INTO movement(id,product_id,branch_id,user_id,kind,quantity,value,created_at,reason) VALUES(1,1,1,1,'adjustment',24,120,'2026-10-01 10:00:00','Old opening')",
          "INSERT INTO cash_session(id,branch_id,user_id,opened_at,closed_at,opening,counted,expected,notes) VALUES(1,1,1,'2026-10-01 10:00:00','2026-10-01 18:00:00',100,100,100,'Closed before upgrade')",
          "INSERT INTO sale(id,number,branch_id,user_id,session_id,created_at,currency,business_name,customer,subtotal,tax,total,cost) VALUES(1,'OLD-SALE',1,1,1,'2026-10-01 12:00:00','KES','Legacy shop','Walk-in',10,0,10,5)",
          "INSERT INTO sale_line(id,sale_id,product_id,sku,name,unit,mode,quantity,conversion,base_quantity,unit_price,discount,tax_rate,subtotal,tax,cost) VALUES(1,1,1,'OLD','Old item','bottle','retail',1,1,1,10,0,0,10,0,5)",
        ]:
            db.session.execute(text(sql))
        db.session.commit()
    return app


def test_upgrade_preserves_legacy_history_and_allocates_wholesale(tmp_path):
    app=old_app(tmp_path)
    with app.app_context():
        before=db.session.execute(text('SELECT id,quantity,value,reason FROM movement')).all()
        db.session.rollback();upgrade()
        assert db.session.execute(text('SELECT id,quantity,value,reason FROM movement')).all()==before
        assert db.session.execute(text('SELECT quantity,value,retail_quantity,retail_value FROM stock')).one()==(24,120,0,0)
        assert db.session.execute(text('SELECT unit_price,subtotal FROM sale_line')).one()==(10,10)
        assert db.session.execute(text('SELECT location FROM movement')).scalar()=='legacy'
        assert db.session.execute(text('SELECT opening_mpesa,expected_mpesa,closed_by_id FROM cash_session')).one()==(None,None,None)
        assert db.session.execute(text("SELECT count(*) FROM catalogue_option WHERE name IN ('Food','bottle')")).scalar()==2
        with pytest.raises(Exception):
            db.session.execute(text('UPDATE movement SET quantity=99'))
        db.session.rollback()
        with pytest.raises(Exception):
            db.session.execute(text('UPDATE stock SET retail_quantity=25'))
        db.session.rollback();db.engine.dispose()


def test_upgrade_refuses_open_session_without_modifying_schema(tmp_path):
    app=old_app(tmp_path)
    with app.app_context():
        db.session.execute(text('UPDATE cash_session SET closed_at=NULL'));db.session.commit()
        with pytest.raises(SystemExit) as stopped:
            upgrade()
        assert stopped.value.code == 1
        db.session.rollback()
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0002'
        assert db.session.execute(text('SELECT quantity,value FROM stock')).one()==(24,120)
        db.session.remove();db.engine.dispose()


def test_funds_upgrade_preserves_history_and_marks_old_payments_unknown(tmp_path):
    app=old_app(tmp_path)
    with app.app_context():
        upgrade(revision='0003')
        db.session.execute(text("INSERT INTO supplier(id,name,phone,email,address,details) VALUES(1,'Legacy supplier','','','','')"))
        db.session.execute(text("INSERT INTO purchase(id,supplier_id,branch_id,user_id,created_at,status) VALUES(1,1,1,1,'2026-10-01','received')"))
        db.session.execute(text("INSERT INTO cash_movement(id,session_id,method,amount,reason,user_id,created_at) VALUES(1,1,'cash',10,'Old cash entry',1,'2026-10-01')"))
        db.session.commit();upgrade()
        assert not db.session.execute(text('SELECT payments_tracked FROM purchase')).scalar()
        assert db.session.execute(text('SELECT amount,kind,purchase_id,reverses_id FROM cash_movement')).one()==(10,'settlement',None,None)
        with pytest.raises(Exception):db.session.execute(text("UPDATE cash_movement SET amount=20"))
        db.session.rollback();db.session.remove();db.engine.dispose()


def test_packaging_upgrade_preserves_legacy_receipt_and_triggers(tmp_path):
    app=old_app(tmp_path)
    with app.app_context():
        upgrade(revision='0004')
        before=db.session.execute(text('SELECT id,unit,conversion,unit_price,subtotal FROM sale_line')).all()
        upgrade()
        assert db.session.execute(text('SELECT id,unit,conversion,unit_price,subtotal FROM sale_line')).all()==before
        assert db.session.execute(text('SELECT packaging_key FROM sale_line')).scalar() is None
        assert db.session.execute(text('SELECT packages FROM product')).scalar() is None
        with pytest.raises(Exception):db.session.execute(text("UPDATE sale_line SET unit='changed'"))
        db.session.rollback();db.session.remove();db.engine.dispose()
