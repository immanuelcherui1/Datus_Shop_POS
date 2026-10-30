import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from functools import wraps
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies
from sqlalchemy import select, func, case
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
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def record(row):
    return serial({column.name: getattr(row, column.name) for column in row.__table__.columns})


def sale_record(sale):
    result = record(sale)
    result['served_by'] = sale.served_by or db.session.get(User, sale.user_id).username
    result['transaction_type'] = sale.transaction_type or ('mixed (legacy)' if len({service.sale_location(l.mode) for l in sale.lines}) > 1 else service.sale_location(sale.lines[0].mode))
    result['balance'] = str(sale.total - sum((p.amount for p in sale.payments), Decimal('0')))
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
                # PostgreSQL waits for the winning transaction before raising the uniqueness error.
                # Return its committed response directly, rather than an ambiguous conflict.
                winner = db.session.scalar(select(Idempotency).where(Idempotency.user_id == g.user.id,
                    Idempotency.scope == operation, Idempotency.key == key))
                if winner and winner.digest == digest and winner.response is not None:
                    return jsonify(winner.response)
                raise Conflict('This operation key conflicts with another request.')
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
    if request.args.get('low') == '1':
        statement = statement.where(Product.active.is_(True), Stock.quantity <= Product.reorder_level)
    ordering = (Stock.quantity > 0, Stock.quantity > Product.reorder_level, Stock.quantity, Product.name) if request.args.get('sort') == 'stock' else (Product.name,)
    result = page(statement.order_by(*ordering))
    items = []
    for product in result.items:
        item = record(product)
        stock = db.session.get(Stock, (product.id, g.user.branch_id))
        item.update(quantity=str(stock.quantity), inventory_value=str(stock.value), retail_quantity=str(stock.retail_quantity),
            wholesale_quantity=str(stock.quantity-stock.retail_quantity), cost_per_unit=str(service.valuation(stock.value/stock.quantity) if stock.quantity else 0),
            cost_per_pack=str(service.valuation(stock.value/stock.quantity*product.pack_size) if stock.quantity else 0))
        items.append(item)
    return jsonify({'items': items, 'total': result.total, 'pages': result.pages})


@api.post('/products')
@require('catalog')
@mutation('product.create')
def create_product():
    data = body(ProductSchema())
    remember_options(data)
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
    remember_options(data)
    for key, value in data.items():
        setattr(product, key, value)
    service.audit('product.updated', 'product', product.id, {'before': before, 'after': record(product)})
    return record(product)


@api.get('/inventory/movements')
@require('catalog')
def movements():
    statement = select(Movement).where(Movement.branch_id == g.user.branch_id).order_by(Movement.id.desc())
    if request.args.get('product_id'):
        statement = statement.where(Movement.product_id == integer_filter('product_id'))
    result = page(statement)
    return jsonify({'items': [record(x) for x in result.items], 'total': result.total, 'pages': result.pages})


@api.post('/inventory/adjustments')
@require('adjust')
@mutation('stock.adjust')
def adjust():
    data = body(AdjustmentSchema())
    stock = service.lock_stock([data['product_id']])[data['product_id']]
    value = service.valuation(data['quantity'] * data['unit_cost']) if data['quantity'] > 0 else -service.consume_value(stock, -data['quantity'], data['location'])
    service.move(stock, data['quantity'], value, 'adjustment', data['reason'], location=data['location'])
    service.audit('stock.adjusted', 'product', stock.product_id, serial(data))
    return {'quantity': stock.quantity, 'value': stock.value}


@api.get('/inventory/reconciliation')
@require('adjust')
def reconcile():
    return jsonify(reconciliation(g.user.branch_id))


def reconciliation(branch_id):
    # Total and allocation aggregates share one SQL snapshot during live posting.
    totals = select(Movement.product_id, func.sum(Movement.quantity).label('quantity'),
        func.sum(Movement.value).label('value'),
        func.sum(case((Movement.location=='retail',Movement.quantity),else_=0)).label('retail_quantity'),
        func.sum(case((Movement.location=='retail',Movement.value),else_=0)).label('retail_value')
    ).where(Movement.branch_id==branch_id).group_by(Movement.product_id).subquery()
    rows = db.session.execute(select(Stock,totals.c.quantity,totals.c.value,totals.c.retail_quantity,totals.c.retail_value)
        .outerjoin(totals,Stock.product_id==totals.c.product_id).where(Stock.branch_id==branch_id)).all()
    discrepancies=[]
    for stock,q,v,rq,rv in rows:
        for allocation,cached_q,cached_v,ledger_q,ledger_v in [('total',stock.quantity,stock.value,q or 0,v or 0),
                ('retail',stock.retail_quantity,stock.retail_value,rq or 0,rv or 0)]:
            if cached_q!=ledger_q or cached_v!=ledger_v:
                discrepancies.append(dict(product_id=stock.product_id,allocation=allocation,cached_quantity=str(cached_q),
                    ledger_quantity=str(ledger_q),cached_value=str(cached_v),ledger_value=str(ledger_v)))
    return {'ok':not discrepancies,'checked':len(rows),'discrepancies':discrepancies}


@api.get('/suppliers')
@require('purchase')
def suppliers():
    result = page(select(Supplier).order_by(Supplier.name))
    return jsonify({'items': [record(x) for x in result.items], 'pages': result.pages, 'total': result.total})


@api.post('/suppliers')
@require('purchase')
@mutation('supplier.create')
def create_supplier():
    data = body(SupplierSchema())
    check_supplier(data)
    supplier = Supplier(**data)
    db.session.add(supplier)
    db.session.flush()
    service.audit('supplier.created', 'supplier', supplier.id)
    return record(supplier)


@api.get('/purchases')
@require('purchase')
def purchases():
    result = page(select(Purchase).where(Purchase.branch_id == g.user.branch_id).order_by(Purchase.id.desc()))
    return jsonify({'items': [purchase_record(x) for x in result.items],
                    'total': result.total, 'pages': result.pages})


@api.post('/purchases')
@require('purchase')
@mutation('purchase.create')
def create_purchase():
    data = body(PurchaseSchema())
    purchase = Purchase(branch_id=g.user.branch_id, user_id=g.user.id, supplier_id=data['supplier_id'])
    save_purchase(purchase, data)
    service.audit('purchase.created', 'purchase', purchase.id)
    return purchase_record(purchase)


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
    if request.args.get('user_id'):
        statement = statement.where(Sale.user_id == integer_filter('user_id'))
    if request.args.get('type'):
        statement = statement.where(Sale.transaction_type == request.args['type'])
    if request.args.get('method'):
        methods = ['external_bank','external_card'] if request.args['method'] == 'other' else [request.args['method']]
        statement = statement.where(Sale.payments.any(Payment.method.in_(methods)))
    if request.args.get('start') or request.args.get('end'):
        start, end = date_range()
        statement = statement.where(Sale.created_at >= start, Sale.created_at < end)
    result = page(statement.order_by(Sale.id.desc()))
    return jsonify({'items': [sale_record(x) for x in result.items], 'total': result.total, 'pages': result.pages})


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


def expected_cash(session, method='cash'):
    amount = db.session.scalar(select(func.coalesce(func.sum(CashMovement.amount), 0)).where(CashMovement.session_id == session.id, CashMovement.method == method))
    return (session.opening if method == 'cash' else session.opening_mpesa) + amount


@api.get('/register')
@require('register')
def register():
    session = db.session.scalar(select(CashSession).where(CashSession.branch_id == g.user.branch_id,
        CashSession.closed_at.is_(None)))
    return jsonify(session_record(session) if session else None)


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
    expected_mpesa = expected_cash(session, 'external_mobile')
    if data['counted'] != expected or data['counted_mpesa'] != expected_mpesa:
        allowed('adjust')
        if len(data['notes'].strip()) < 5:
            raise BadRequest('Explain the cash or M-Pesa variance in Remarks.')
    session.counted, session.expected, session.notes = data['counted'], expected, data['notes']
    session.counted_mpesa, session.expected_mpesa = data['counted_mpesa'], expected_mpesa
    session.closed_by_id = g.user.id
    session.closed_at = now()
    service.audit('register.closed', 'cash_session', session.id, {'variance': str(session.counted - expected), 'variance_mpesa': str(session.counted_mpesa - expected_mpesa)})
    return session_record(session)


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


# Catalogue labels remain compatible with historical products; saved options are reusable.
def remember_options(data):
    for kind,key in [('category','category'),('unit','unit'),('unit','packaging_unit')]:
        name = data[key].strip()
        if not name:
            raise BadRequest('Catalogue labels cannot be blank.')
        existing = db.session.scalar(select(CatalogueOption).where(CatalogueOption.kind==kind,func.lower(CatalogueOption.name)==name.lower()))
        data[key] = existing.name if existing else name
        if not existing:
            db.session.add(CatalogueOption(kind=kind,name=name))
            db.session.flush()


@api.get('/catalogue-options')
@require('catalog')
def catalogue_options():
    return jsonify([record(x) for x in db.session.scalars(select(CatalogueOption).order_by(CatalogueOption.name))])


@api.post('/catalogue-options')
@require('catalog')
@mutation('catalogue.create')
def add_catalogue_option():
    data = body(CatalogueSchema())
    data['name'] = data['name'].strip()
    if not data['name'] or (data['kind']=='unit' and len(data['name'])>30):
        raise BadRequest('Unit labels must contain 1–30 characters.')
    existing = db.session.scalar(select(CatalogueOption).where(CatalogueOption.kind==data['kind'],func.lower(CatalogueOption.name)==data['name'].lower()))
    if existing:
        return record(existing)
    row = CatalogueOption(**data)
    db.session.add(row); db.session.flush()
    service.audit('catalogue.created','catalogue_option',row.id)
    return record(row)


@api.post('/inventory/transfers')
@require('adjust')
@mutation('stock.transfer')
def transfer_stock():
    return service.transfer(body(TransferSchema()))


def check_supplier(data, exclude=None):
    data['name'] = data['name'].strip()
    if not data['name']:
        raise BadRequest('Supplier name is required.')
    query = select(Supplier).where(func.lower(Supplier.name)==data['name'].lower())
    if exclude:
        query = query.where(Supplier.id!=exclude)
    if db.session.scalar(query):
        raise Conflict('A supplier with this name already exists. Edit the existing supplier.')


@api.put('/suppliers/<int:supplier_id>')
@require('purchase')
@mutation('supplier.update')
def update_supplier(supplier_id):
    row = db.session.get(Supplier,supplier_id)
    if not row:
        raise NotFound()
    data = body(SupplierSchema()); check_supplier(data,supplier_id)
    before = record(row)
    for key,value in data.items():
        setattr(row,key,value)
    service.audit('supplier.updated','supplier',row.id,{'before':before,'after':record(row)})
    return record(row)


def purchase_record(purchase):
    return dict(record(purchase), lines=[record(l) for l in purchase.lines],
        supplier=record(db.session.get(Supplier,purchase.supplier_id)),
        prepared_by=db.session.get(User,purchase.user_id).username,
        business_name=current_app.config['BUSINESS_NAME'], currency=current_app.config['CURRENCY'],
        total=str(service.money(sum((l.quantity*l.unit_cost for l in purchase.lines),Decimal('0')))))


def save_purchase(purchase, data):
    service.unique_lines(data['lines'],'product_id')
    if not db.session.get(Supplier,data['supplier_id']):
        raise BadRequest('Unknown supplier.')
    service.lock_stock([l['product_id'] for l in data['lines']])
    purchase.supplier_id, purchase.status = data['supplier_id'], data['status']
    db.session.add(purchase); db.session.flush()
    for values in data['lines']:
        p = db.session.scalar(select(Product).where(Product.id==values['product_id']).with_for_update())
        if not p.active:
            raise BadRequest('Inactive products cannot be ordered.')
        conversion = p.pack_size if values['purchase_unit']=='pack' else Decimal('1')
        purchase.lines.append(PurchaseLine(product_id=p.id, quantity=values['quantity']*conversion,
            unit_cost=service.valuation(values['unit_cost']/conversion), description=p.name,
            unit=p.packaging_unit if values['purchase_unit']=='pack' else p.unit,
            conversion=conversion, ordered_quantity=values['quantity'], ordered_unit_cost=values['unit_cost']))
    db.session.flush()


@api.put('/purchases/<int:purchase_id>')
@require('purchase')
@mutation('purchase.edit')
def edit_purchase(purchase_id):
    purchase = scoped(db.session.scalar(select(Purchase).where(Purchase.id==purchase_id).with_for_update()))
    if purchase.status!='draft':
        raise Conflict('Only draft purchase orders can be edited.')
    for line in list(purchase.lines):
        db.session.delete(line)
    db.session.flush()
    db.session.expire(purchase, ['lines'])
    save_purchase(purchase,body(PurchaseSchema()))
    service.audit('purchase.updated','purchase',purchase.id)
    return purchase_record(purchase)


def session_record(session):
    result = record(session)
    result['opened_by'] = db.session.get(User,session.user_id).username
    result['closed_by'] = db.session.get(User,session.closed_by_id).username if session.closed_by_id else None
    for suffix,method in [('', 'cash'),('_mpesa','external_mobile')]:
        expected = getattr(session,'expected'+suffix) if session.closed_at else expected_cash(session,method)
        result['expected'+suffix] = expected
        result['transactions'+suffix] = expected-getattr(session,'opening'+suffix) if expected is not None else None
        counted = getattr(session,'counted'+suffix)
        result['variance'+suffix] = counted-expected if counted is not None and expected is not None else None
    return serial(result)


@api.get('/register/history')
@require()
def session_history():
    if not ({'register','report','audit'} & PERMISSIONS[g.user.role]):
        allowed('register')
    result = page(select(CashSession).where(CashSession.branch_id==g.user.branch_id).order_by(CashSession.id.desc()))
    return jsonify({'items':[session_record(s) for s in result.items],'pages':result.pages,'total':result.total})


def date_range():
    tz = ZoneInfo(current_app.config['BUSINESS_TIMEZONE'])
    today = datetime.now(tz).date().isoformat()
    try:
        start = date.fromisoformat(request.args.get('start',today))
        end = date.fromisoformat(request.args.get('end',today))
    except ValueError:
        raise BadRequest('Use YYYY-MM-DD dates.')
    if end<start or (end-start).days>366:
        raise BadRequest('Select a date range of at most 367 days.')
    return datetime.combine(start,time.min,tzinfo=tz).astimezone(timezone.utc), datetime.combine(end+timedelta(days=1),time.min,tzinfo=tz).astimezone(timezone.utc)


@api.get('/reports/insights')
@require('report')
def insights():
    start,end = date_range()
    tz = ZoneInfo(current_app.config['BUSINESS_TIMEZONE'])
    sold = db.session.execute(select(SaleLine.product_id,func.sum(SaleLine.base_quantity),func.sum(SaleLine.subtotal+SaleLine.tax))
        .join(Sale).where(Sale.branch_id==g.user.branch_id,Sale.created_at>=start,Sale.created_at<end).group_by(SaleLine.product_id)).all()
    volume = {pid:q for pid,q,_ in sold}
    rows = db.session.execute(select(Product,Stock).join(Stock).where(Stock.branch_id==g.user.branch_id,Product.active.is_(True))).all()
    items = [dict(record(p),quantity=s.quantity,retail_quantity=s.retail_quantity,wholesale_quantity=s.quantity-s.retail_quantity,
        inventory_value=s.value,cost_per_unit=service.valuation(s.value/s.quantity) if s.quantity else Decimal('0'),
        cost_per_pack=service.valuation(s.value/s.quantity*p.pack_size) if s.quantity else Decimal('0'),sold_units=volume.get(p.id,Decimal('0'))) for p,s in rows]
    moving = sorted([p for p in items if p['sold_units']>0],key=lambda p:p['sold_units'],reverse=True)
    # Explicit relative classification: top quartile of products with sales is fast-moving.
    fast = moving[:max(1,(len(moving)+3)//4)] if moving else []
    slow = moving[len(fast):]
    nonmoving = [p for p in items if not p['sold_units']]
    today = datetime.now(tz).date()
    expiring = [p for p in items if p['expiry_date'] and p['quantity']>0 and date.fromisoformat(p['expiry_date'])<=today+timedelta(days=30)]
    sales_rows = db.session.scalars(select(Sale).where(Sale.branch_id==g.user.branch_id,Sale.created_at>=start,Sale.created_at<end)).all()
    trends, channels, payments = {}, {}, {'Cash':Decimal('0'),'M-Pesa':Decimal('0'),'Other':Decimal('0')}
    for sale in sales_rows:
        day = (sale.created_at.replace(tzinfo=timezone.utc) if sale.created_at.tzinfo is None else sale.created_at).astimezone(tz).date().isoformat()
        trends[day] = trends.get(day,Decimal('0'))+sale.total
        channel = sale.transaction_type or 'legacy'
        channels[channel] = channels.get(channel,Decimal('0'))+sale.total
        for p in sale.payments:
            label = 'Cash' if p.method=='cash' else 'M-Pesa' if p.method=='external_mobile' else 'Other'
            payments[label] += p.amount
    movement_rows = db.session.execute(select(Movement.created_at,Movement.quantity,Movement.kind).where(
        Movement.branch_id==g.user.branch_id,Movement.created_at>=start,Movement.created_at<end)).all()
    movements = {}
    for dt,q,kind in movement_rows:
        if kind in ('transfer_in','transfer_out'):
            continue
        day = (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(tz).date().isoformat()
        movements[day] = movements.get(day,Decimal('0'))+q
    return jsonify(serial({'total_products':db.session.scalar(select(func.count(Product.id)).join(Stock).where(Stock.branch_id==g.user.branch_id)), 'active_products':len(items),'out_of_stock':[p for p in items if p['quantity']==0],
        'low_stock':[p for p in items if p['quantity']<=Decimal(p['reorder_level'])], 'expiring':expiring,
        'inventory_value':sum((p['inventory_value'] for p in items),Decimal('0')),
        'fast':fast,'slow':slow,'nonmoving':nonmoving,'best_selling':moving[:10],
        'sales_trend':dict(sorted(trends.items())),'stock_trend':dict(sorted(movements.items())),
        'channels':channels,'payments':payments}))


def integer_filter(name):
    try:
        value = int(request.args[name])
        if value < 1:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise BadRequest(f'{name} must be a positive integer.')
