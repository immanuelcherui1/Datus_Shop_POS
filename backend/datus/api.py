import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from functools import wraps
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, Unauthorized, NotFound
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db, limiter
from .models import *
from .schemas import *
from .security import require, allowed, scoped, PERMISSIONS
from . import services as service

api = Blueprint('api', __name__, url_prefix='/api')


def serial(value):
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, datetime):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def record(row):
    return serial({column.name: getattr(row, column.name) for column in row.__table__.columns})


def sale_record(sale):
    result = record(sale)
    result['lines'] = [record(line) for line in sale.lines]
    result['payments'] = [record(payment) for payment in sale.payments]
    return result


def body(schema):
    if not request.is_json:
        raise BadRequest('Expected an application/json request.')
    return schema.load(request.get_json())


def mutation(scope):
    """Claim a retry key and commit its saved response with the business transaction."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            key = request.headers.get('Idempotency-Key', '')
            if not 8 <= len(key) <= 100:
                raise BadRequest('An Idempotency-Key of 8–100 characters is required.')
            digest = hashlib.sha256(json.dumps(request.get_json(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            operation = scope + ':' + request.path
            existing = db.session.scalar(select(Idempotency).where(Idempotency.user_id == g.user.id,
                Idempotency.scope == operation, Idempotency.key == key))
            if existing:
                if existing.digest != digest:
                    raise Conflict('This retry key was already used for different data.')
                return jsonify(existing.response)
            retry = Idempotency(user_id=g.user.id, scope=operation, key=key, digest=digest)
            db.session.add(retry)
            try:
                # Unique constraint serializes concurrent claims. On collision a retry returns the winner.
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                raise Conflict('Another request used this key. Retry the same request to retrieve its result.')
            response = serial(fn(*args, **kwargs))
            retry.response = response
            db.session.commit()
            return jsonify(response)
        return wrapped
    return decorate


def page(statement):
    try:
        number = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 50))))
    except ValueError:
        raise BadRequest('Invalid pagination.')
    result = db.paginate(statement, page=number, per_page=size, error_out=False)
    return result


@api.post('/auth/login')
@limiter.limit('10 per minute')
def login():
    data = body(LoginSchema())
    user = db.session.scalar(select(User).where(User.username == data['username']))
    # Always hash-check, including unknown users, to reduce username timing differences.
    valid = check_password_hash(user.password_hash if user else current_app.config['DUMMY_PASSWORD_HASH'], data['password'])
    if not user or not valid or not user.active:
        raise Unauthorized('Invalid username or password.')
    token = create_access_token(identity=str(user.id), additional_claims={'version': user.token_version})
    response = jsonify({'id': user.id, 'username': user.username, 'role': user.role})
    set_access_cookies(response, token)
    return response


@api.post('/auth/logout')
@require()
def logout():
    g.user.token_version += 1
    db.session.commit()
    response = jsonify({'ok': True})
    unset_jwt_cookies(response)
    return response


@api.get('/auth/me')
@require()
def me():
    return jsonify({'id': g.user.id, 'username': g.user.username, 'role': g.user.role,
        'permissions': sorted(PERMISSIONS[g.user.role]), 'branch_id': g.user.branch_id,
        'business_name': current_app.config['BUSINESS_NAME'], 'currency': current_app.config['CURRENCY'],
        'timezone': current_app.config['BUSINESS_TIMEZONE']})


@api.get('/products')
@require()
def products():
    statement = select(Product).join(Stock, Stock.product_id == Product.id).where(Stock.branch_id == g.user.branch_id)
    query = request.args.get('q', '').strip()[:160]
    if query:
        statement = statement.where(db.or_(Product.name.icontains(query, autoescape=True),
            Product.sku.icontains(query, autoescape=True), Product.barcode == query))
    result = page(statement.order_by(Product.name))
    items = []
    for product in result.items:
        item = record(product)
        stock = db.session.get(Stock, (product.id, g.user.branch_id))
        item.update(quantity=str(stock.quantity), inventory_value=str(stock.value))
        items.append(item)
    return jsonify({'items': items, 'total': result.total, 'pages': result.pages})


@api.post('/products')
@require('catalog')
@mutation('product.create')
def create_product():
    data = body(ProductSchema())
    product = Product(**data)
    db.session.add(product)
    db.session.flush()
    db.session.add(Stock(product_id=product.id, branch_id=g.user.branch_id, quantity=0, value=0))
    service.audit('product.created', 'product', product.id)
    return record(product)


@api.put('/products/<int:product_id>')
@require('catalog')
@mutation('product.update')
def update_product(product_id):
    product = db.session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product or not db.session.get(Stock, (product_id, g.user.branch_id)):
        raise NotFound()
    before = record(product)
    data = body(ProductSchema())
    for key, value in data.items():
        setattr(product, key, value)
    service.audit('product.updated', 'product', product.id, {'before': before, 'after': record(product)})
    return record(product)


@api.get('/inventory/movements')
@require('catalog')
def movements():
    statement = select(Movement).where(Movement.branch_id == g.user.branch_id).order_by(Movement.id.desc())
    if request.args.get('product_id'):
        statement = statement.where(Movement.product_id == request.args['product_id'])
    result = page(statement)
    return jsonify({'items': [record(x) for x in result.items], 'total': result.total, 'pages': result.pages})


@api.post('/inventory/adjustments')
@require('adjust')
@mutation('stock.adjust')
def adjust():
    data = body(AdjustmentSchema())
    stock = service.lock_stock([data['product_id']])[data['product_id']]
    value = service.valuation(data['quantity'] * data['unit_cost']) if data['quantity'] > 0 else -service.consume_value(stock, -data['quantity'])
    service.move(stock, data['quantity'], value, 'adjustment', data['reason'])
    service.audit('stock.adjusted', 'product', stock.product_id, serial(data))
    return {'quantity': stock.quantity, 'value': stock.value}


@api.get('/inventory/reconciliation')
@require('adjust')
def reconcile():
    return jsonify(reconciliation(g.user.branch_id))


def reconciliation(branch_id):
    # One aggregate statement provides a consistent snapshot, even during live posting.
    totals = select(Movement.product_id, func.sum(Movement.quantity).label('quantity'),
        func.sum(Movement.value).label('value')).where(Movement.branch_id == branch_id).group_by(Movement.product_id).subquery()
    rows = db.session.execute(select(Stock, totals.c.quantity, totals.c.value).outerjoin(
        totals, Stock.product_id == totals.c.product_id).where(Stock.branch_id == branch_id)).all()
    discrepancies = [dict(product_id=s.product_id, cached_quantity=str(s.quantity), ledger_quantity=str(q or 0),
        cached_value=str(s.value), ledger_value=str(v or 0)) for s, q, v in rows if s.quantity != (q or 0) or s.value != (v or 0)]
    return {'ok': not discrepancies, 'checked': len(rows), 'discrepancies': discrepancies}


@api.get('/suppliers')
@require('purchase')
def suppliers():
    result = page(select(Supplier).order_by(Supplier.name))
    return jsonify({'items': [record(x) for x in result.items], 'pages': result.pages, 'total': result.total})


@api.post('/suppliers')
@require('purchase')
@mutation('supplier.create')
def create_supplier():
    supplier = Supplier(**body(SupplierSchema()))
    db.session.add(supplier)
    db.session.flush()
    service.audit('supplier.created', 'supplier', supplier.id)
    return record(supplier)


@api.get('/purchases')
@require('purchase')
def purchases():
    result = page(select(Purchase).where(Purchase.branch_id == g.user.branch_id).order_by(Purchase.id.desc()))
    return jsonify({'items': [dict(record(x), lines=[record(line) for line in x.lines]) for x in result.items],
                    'total': result.total, 'pages': result.pages})


@api.post('/purchases')
@require('purchase')
@mutation('purchase.create')
def create_purchase():
    data = body(PurchaseSchema())
    service.unique_lines(data['lines'], 'product_id')
    if not db.session.get(Supplier, data['supplier_id']):
        raise BadRequest('Unknown supplier.')
    service.lock_stock([line['product_id'] for line in data['lines']])
    purchase = Purchase(supplier_id=data['supplier_id'], branch_id=g.user.branch_id, user_id=g.user.id)
    db.session.add(purchase)
    db.session.flush()
    for line in data['lines']:
        db.session.add(PurchaseLine(purchase_id=purchase.id, **line))
    service.audit('purchase.ordered', 'purchase', purchase.id)
    db.session.flush()
    return dict(record(purchase), lines=[record(line) for line in purchase.lines])


@api.post('/purchases/<int:purchase_id>/receipts')
@require('purchase')
@mutation('purchase.receive')
def receive_purchase(purchase_id):
    return record(service.receive(purchase_id, body(ReceiveSchema())))


@api.post('/sales/quote')
@require('sell')
def quote():
    return jsonify(serial(service.quote(body(QuoteSchema()))))


@api.post('/sales')
@require('sell')
@mutation('sale.post')
def checkout():
    return sale_record(service.checkout(body(CheckoutSchema())))


@api.get('/sales')
@require()
def sales():
    if 'sell' not in PERMISSIONS[g.user.role] and 'report' not in PERMISSIONS[g.user.role]:
        allowed('sell')
    statement = select(Sale).where(Sale.branch_id == g.user.branch_id)
    if g.user.role == 'cashier':
        statement = statement.where(Sale.user_id == g.user.id)
    result = page(statement.order_by(Sale.id.desc()))
    return jsonify({'items': [record(x) for x in result.items], 'total': result.total, 'pages': result.pages})


@api.get('/sales/<int:sale_id>')
@require()
def sale_detail(sale_id):
    sale = scoped(db.session.get(Sale, sale_id))
    if g.user.role == 'cashier' and sale.user_id != g.user.id:
        raise NotFound()
    if not ({'sell', 'report'} & PERMISSIONS[g.user.role]):
        allowed('sell')
    return jsonify(sale_record(sale))


@api.post('/sales/<int:sale_id>/returns')
@require('refund')
@mutation('sale.return')
def return_sale(sale_id):
    return record(service.post_return(sale_id, body(ReturnSchema())))


def expected_cash(session):
    amount = db.session.scalar(select(func.coalesce(func.sum(CashMovement.amount), 0)).where(CashMovement.session_id == session.id))
    return session.opening + amount


@api.get('/register')
@require('register')
def register():
    session = db.session.scalar(select(CashSession).where(CashSession.branch_id == g.user.branch_id,
        CashSession.closed_at.is_(None)))
    return jsonify(dict(record(session), expected=str(expected_cash(session))) if session else None)


@api.post('/register/open')
@require('register')
@mutation('register.open')
def open_register():
    session = CashSession(branch_id=g.user.branch_id, user_id=g.user.id, **body(OpenSessionSchema()))
    db.session.add(session)
    db.session.flush()
    service.audit('register.opened', 'cash_session', session.id)
    return record(session)


@api.post('/register/close')
@require('register')
@mutation('register.close')
def close_register():
    data = body(CloseSessionSchema())
    session = service.open_register()
    expected = expected_cash(session)
    if data['counted'] != expected:
        allowed('adjust')
        if len(data['notes'].strip()) < 5:
            raise BadRequest('Explain the cash variance in closing notes.')
    session.counted, session.expected, session.notes = data['counted'], expected, data['notes']
    session.closed_at = now()
    service.audit('register.closed', 'cash_session', session.id, {'variance': str(session.counted - expected)})
    return dict(record(session), variance=str(session.counted - expected))


@api.get('/reports/daily')
@require('report')
def daily():
    tz = ZoneInfo(current_app.config['BUSINESS_TIMEZONE'])
    try:
        day = datetime.strptime(request.args.get('date', datetime.now(tz).date().isoformat()), '%Y-%m-%d').date()
    except ValueError:
        raise BadRequest('Date must be YYYY-MM-DD.')
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    where = (Sale.branch_id == g.user.branch_id, Sale.created_at >= start, Sale.created_at < end)
    count, subtotal, tax, total, cost = db.session.execute(select(func.count(Sale.id),
        func.coalesce(func.sum(Sale.subtotal), 0), func.coalesce(func.sum(Sale.tax), 0),
        func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(Sale.cost), 0)).where(*where)).one()
    payments = db.session.execute(select(Payment.method, func.sum(Payment.amount)).join(Sale).where(*where).group_by(Payment.method)).all()
    return_filter = (Sale.branch_id == g.user.branch_id, Return.created_at >= start, Return.created_at < end)
    refunded, return_tax, return_cost = db.session.execute(select(func.coalesce(func.sum(Return.amount), 0),
        func.coalesce(func.sum(Return.tax), 0), func.coalesce(func.sum(Return.cost), 0)).join(Sale).where(*return_filter)).one()
    # Damaged returns remain a cost: only restocked goods reverse cost of goods sold.
    restocked_cost = db.session.scalar(select(func.coalesce(func.sum(ReturnLine.cost), 0)).join(Return).join(Sale).where(
        *return_filter, ReturnLine.disposition == 'restock'))
    low = db.session.scalar(select(func.count()).select_from(Stock).join(Product).where(
        Stock.branch_id == g.user.branch_id, Product.active.is_(True), Stock.quantity <= Product.reorder_level))
    return jsonify(serial({'date': day.isoformat(), 'currency': current_app.config['CURRENCY'],
        'transactions': count, 'sales_including_tax': total, 'subtotal': subtotal, 'tax': tax,
        'refunds': refunded, 'net_revenue_excluding_tax': subtotal - refunded + return_tax,
        'net_tax': tax - return_tax, 'cost_of_goods_sold': cost - restocked_cost,
        'gross_profit': subtotal - refunded + return_tax - cost + restocked_cost,
        'average_sale': service.money(total / count) if count else Decimal('0.00'),
        'low_stock_items': low, 'payments': {method: amount for method, amount in payments}}))


@api.get('/users')
@require('users')
def users():
    return jsonify([{'id': x.id, 'username': x.username, 'role': x.role, 'active': x.active}
        for x in db.session.scalars(select(User).where(User.branch_id == g.user.branch_id))])


@api.post('/users')
@require('users')
@mutation('user.create')
def create_user():
    data = body(UserSchema())
    user = User(username=data['username'], role=data['role'], password_hash=generate_password_hash(data['password']),
        branch_id=g.user.branch_id)
    db.session.add(user)
    db.session.flush()
    service.audit('user.created', 'user', user.id, {'role': user.role})
    return {'id': user.id, 'username': user.username, 'role': user.role}


@api.get('/audit')
@require('audit')
def audits():
    result = page(select(Audit).where(Audit.branch_id == g.user.branch_id).order_by(Audit.id.desc()))
    return jsonify({'items': [record(x) for x in result.items], 'pages': result.pages, 'total': result.total})
