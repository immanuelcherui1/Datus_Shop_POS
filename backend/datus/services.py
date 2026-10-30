"""Posting services. Caller owns commit/rollback; no service commits halfway through."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from flask import current_app, g
from sqlalchemy import select, func
from werkzeug.exceptions import BadRequest, Conflict
from .extensions import db
from .models import (Product, Stock, Movement, Audit, Purchase, PurchaseLine, Receipt, User,
                     Sale, SaleLine, Payment, CashSession, CashMovement, Return, ReturnLine, Refund)
from .security import allowed, scoped

ZERO = Decimal('0')


def money(value):
    return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def valuation(value):
    return value.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)


def audit(action, entity, entity_id, details=None):
    db.session.add(Audit(user_id=g.user.id, branch_id=g.user.branch_id,
                         action=action, entity=entity, entity_id=entity_id, details=details or {}))


def unique_lines(lines, field):
    ids = [line[field] for line in lines]
    if len(ids) != len(set(ids)):
        raise BadRequest('Duplicate lines are not allowed. Combine quantities first.')


def lock_stock(product_ids):
    # Product creation installs zero-balance rows. Lock in product-ID order to avoid deadlocks.
    rows = db.session.scalars(select(Stock).where(
        Stock.branch_id == g.user.branch_id, Stock.product_id.in_(product_ids)
    ).order_by(Stock.product_id).with_for_update()).all()
    if len(rows) != len(set(product_ids)):
        raise BadRequest('One or more products are unavailable at this branch.')
    return {row.product_id: row for row in rows}


def pool(stock, location):
    if location == 'retail':
        return stock.retail_quantity, stock.retail_value
    return stock.quantity - stock.retail_quantity, stock.value - stock.retail_value


def move(stock, quantity, value, kind, reason, location='wholesale', **links):
    if quantity == 0:
        raise BadRequest('Stock movement cannot be zero.')
    available, worth = pool(stock, location)
    if available + quantity < 0 or valuation(worth + value) < 0:
        raise Conflict(f'Insufficient {location} stock or inventory value.')
    stock.quantity += quantity
    stock.value = valuation(stock.value + value)
    if location == 'retail':
        stock.retail_quantity += quantity
        stock.retail_value = valuation(stock.retail_value + value)
    db.session.add(Movement(product_id=stock.product_id, branch_id=stock.branch_id,
        user_id=g.user.id, quantity=quantity, value=value, kind=kind, reason=reason,
        location=location, **links))


def consume_value(stock, quantity, location='wholesale'):
    available, worth = pool(stock, location)
    if quantity > available or available <= 0:
        raise Conflict(f'Insufficient {location} stock.' + (' Allocate goods to retail before retail selling.' if location == 'retail' else ''))
    return worth if quantity == available else valuation(worth * quantity / available)


def transfer(data):
    stock = lock_stock([data['product_id']])[data['product_id']]
    product = db.session.scalar(select(Product).where(Product.id == stock.product_id).with_for_update())
    quantity = data['quantity'] * (product.pack_size if data['unit'] == 'pack' else 1)
    cost = consume_value(stock, quantity)
    reference = 'TR-' + uuid4().hex[:16].upper()
    # Both ledger legs and caches commit together under the same stock-row lock.
    move(stock, -quantity, -cost, 'transfer_out', data['reason'], transfer_reference=reference)
    move(stock, quantity, cost, 'transfer_in', data['reason'], location='retail', transfer_reference=reference)
    audit('stock.transferred', 'product', product.id, {'reference':reference,'quantity':str(quantity)})
    return {'reference':reference,'quantity':quantity,'wholesale_quantity':pool(stock,'wholesale')[0], 'retail_quantity':stock.retail_quantity}


def sale_location(mode):
    return 'wholesale' if mode.startswith('wholesale') else 'retail'


def quote(data):
    keys = [(line['product_id'], line['mode']) for line in data['lines']]
    if len(keys) != len(set(keys)):
        raise BadRequest('Combine duplicate product and selling-unit lines.')
    types = {sale_location(item['mode']) for item in data['lines']}
    if len(types) != 1:
        raise BadRequest('Wholesale and retail require separate transactions.')
    result = []
    for item in data['lines']:
        product = db.session.get(Product, item['product_id'])
        if not product or not product.active:
            raise BadRequest('Product is missing or inactive.')
        conversion = product.pack_size if item['mode'] in ('wholesale', 'retail_pack') else Decimal('1')
        price = {'wholesale': product.wholesale_price, 'wholesale_unit': valuation(product.wholesale_price / product.pack_size),
                 'retail': product.retail_price, 'retail_pack': product.retail_price * product.pack_size}[item['mode']]
        base_quantity = item['quantity'] * conversion
        if base_quantity != base_quantity.quantize(Decimal('.001')):
            raise BadRequest('This pack quantity requires more than three base-unit decimals.')
        if item['discount']:
            allowed('discount')
        gross = money(price * item['quantity'])
        if item['discount'] > gross:
            raise BadRequest('Discount exceeds the line amount.')
        subtotal = gross - item['discount']
        tax = money(subtotal * product.tax_rate)
        result.append(dict(product_id=product.id, sku=product.sku, name=product.name,
            unit=product.packaging_unit if item['mode'] in ('wholesale', 'retail_pack') else product.unit, mode=item['mode'], quantity=item['quantity'], conversion=conversion,
            base_quantity=base_quantity, unit_price=price, discount=item['discount'],
            tax_rate=product.tax_rate, subtotal=subtotal, tax=tax))
    subtotal = sum((line['subtotal'] for line in result), ZERO)
    tax = sum((line['tax'] for line in result), ZERO)
    return dict(lines=result, subtotal=subtotal, tax=tax, total=subtotal + tax)


def open_register():
    session = db.session.scalar(select(CashSession).where(CashSession.branch_id == g.user.branch_id,
        CashSession.closed_at.is_(None)).with_for_update())
    if not session:
        raise Conflict('Open a cash register session first.')
    return session


def checkout(data):
    register = open_register()
    stocks = lock_stock([line['product_id'] for line in data['lines']])
    # Lock catalogue rows as well, so a concurrent price edit cannot race finalization.
    db.session.scalars(select(Product).where(Product.id.in_(stocks)).order_by(Product.id).with_for_update()).all()
    calculated = quote(data)
    if sum((p['amount'] for p in data['payments']), ZERO) != calculated['total']:
        raise BadRequest('Payments must equal the exact total. Record cash net of change.')
    if calculated['total'] <= 0:
        raise BadRequest('A completed sale must have a positive total.')
    sale = Sale(number='DT-' + uuid4().hex[:16].upper(), branch_id=g.user.branch_id,
        user_id=g.user.id, session_id=register.id, currency=current_app.config['CURRENCY'],
        business_name=current_app.config['BUSINESS_NAME'], customer=data['customer'],
        served_by=g.user.username, transaction_type=sale_location(calculated['lines'][0]['mode']),
        subtotal=calculated['subtotal'], tax=calculated['tax'], total=calculated['total'], cost=ZERO)
    # Set cost before first flush: posted rows cannot be updated, even by this service.
    # Pack and unit lines may share a product. Reserve their combined quantity and
    # cost in order so the final line consumes valuation rounding residue exactly.
    remaining = {pid: pool(stock, sale.transaction_type) for pid,stock in stocks.items()}
    costs = []
    for line in calculated['lines']:
        available, worth = remaining[line['product_id']]
        quantity = line['base_quantity']
        if quantity > available or available <= 0:
            raise Conflict(f'Insufficient {sale.transaction_type} stock for the combined pack and unit quantities.')
        cost = worth if quantity == available else valuation(worth * quantity / available)
        costs.append(cost)
        remaining[line['product_id']] = (available - quantity, worth - cost)
    sale.cost = sum(costs, ZERO)
    db.session.add(sale)
    db.session.flush()
    for values, cost in zip(calculated['lines'], costs):
        line = SaleLine(sale_id=sale.id, cost=cost, **values)
        db.session.add(line)
        db.session.flush()
        move(stocks[line.product_id], -line.base_quantity, -cost, 'sale', sale.number, location=sale_location(line.mode), sale_line_id=line.id)
    for values in data['payments']:
        if values['method'] != 'cash':
            # Manual settlement evidence is deliberately distinct from an integrated provider callback.
            allowed('external')
            if not values['reference']:
                raise BadRequest('An independently verified external settlement reference is required.')
        elif values['reference']:
            raise BadRequest('Cash must not have an external payment reference.')
        payment = Payment(sale_id=sale.id, user_id=g.user.id, **values)
        db.session.add(payment)
        db.session.flush()
        if payment.method in ('cash', 'external_mobile'):
            db.session.add(CashMovement(session_id=register.id, payment_id=payment.id, method=payment.method,
                amount=payment.amount, reason=sale.number, user_id=g.user.id))
    audit('sale.posted', 'sale', sale.id, {'number': sale.number})
    # Optional fault injection used only by the test suite to prove full rollback.
    if current_app.testing and current_app.config.get('FAIL_CHECKOUT'):
        raise RuntimeError('Injected checkout failure')
    db.session.flush()
    return sale


def receive(purchase_id, data):
    purchase = scoped(db.session.scalar(select(Purchase).where(Purchase.id == purchase_id).with_for_update()))
    if purchase.status not in ('ordered', 'partial'):
        raise Conflict('Confirm a draft purchase order before receiving goods.')
    unique_lines(data['lines'], 'line_id')
    lines = {line.id: line for line in purchase.lines}
    if any(item['line_id'] not in lines for item in data['lines']):
        raise BadRequest('Receipt line does not belong to this purchase.')
    stocks = lock_stock([lines[item['line_id']].product_id for item in data['lines']])
    receipt = Receipt(purchase_id=purchase.id, user_id=g.user.id)
    db.session.add(receipt)
    db.session.flush()
    for item in data['lines']:
        line = lines[item['line_id']]
        if line.received + item['quantity'] > line.quantity:
            raise Conflict('Received quantity exceeds the outstanding order quantity.')
        line.received += item['quantity']
        move(stocks[line.product_id], item['quantity'], valuation(item['quantity'] * (item['unit_cost'] if item.get('unit_cost') is not None else line.unit_cost)),
             'purchase_receipt', f'Purchase {purchase.id}', receipt_id=receipt.id)
    purchase.status = 'received' if all(line.received == line.quantity for line in lines.values()) else 'partial'
    audit('purchase.received', 'receipt', receipt.id)
    return receipt


def post_return(sale_id, data):
    sale = scoped(db.session.scalar(select(Sale).where(Sale.id == sale_id).with_for_update()))
    register = open_register()
    unique_lines(data['lines'], 'line_id')
    unique_lines(data['refunds'], 'payment_id')
    originals = {line.id: line for line in sale.lines}
    calculated = []
    for item in data['lines']:
        line = originals.get(item['line_id'])
        if not line:
            raise BadRequest('Return line does not belong to the original sale.')
        previous = db.session.execute(select(func.coalesce(func.sum(ReturnLine.quantity), 0),
            func.coalesce(func.sum(ReturnLine.amount), 0), func.coalesce(func.sum(ReturnLine.tax), 0),
            func.coalesce(func.sum(ReturnLine.cost), 0)).where(ReturnLine.sale_line_id == line.id)).one()
        # Preserve eligibility for legacy fractional wholesale sales/returns.
        if (line.mode != 'retail' and line.quantity == line.quantity.to_integral_value()
                and previous[0] == previous[0].to_integral_value()
                and item['quantity'] != item['quantity'].to_integral_value()):
            raise BadRequest('Wholesale returns must use whole packs.')
        cumulative = previous[0] + item['quantity']
        if cumulative > line.quantity:
            raise Conflict('Return exceeds the remaining eligible quantity.')
        # Cumulative rounding makes all partial returns sum exactly to the original amount.
        amount = money((line.subtotal + line.tax) * cumulative / line.quantity) - previous[1]
        tax = money(line.tax * cumulative / line.quantity) - previous[2]
        cost = valuation(line.cost * cumulative / line.quantity) - previous[3]
        calculated.append((line, item, amount, tax, cost))
    amount = sum((x[2] for x in calculated), ZERO)
    if sum((x['amount'] for x in data['refunds']), ZERO) != amount:
        raise BadRequest('Refund allocations must equal the return amount.')
    stocks = lock_stock([x[0].product_id for x in calculated])
    returned = Return(sale_id=sale.id, user_id=g.user.id, reason=data['reason'], amount=amount,
        tax=sum((x[3] for x in calculated), ZERO), cost=sum((x[4] for x in calculated), ZERO))
    db.session.add(returned)
    db.session.flush()
    for line, item, line_amount, tax, cost in calculated:
        row = ReturnLine(return_id=returned.id, sale_line_id=line.id, quantity=item['quantity'],
            disposition=item['disposition'], amount=line_amount, tax=tax, cost=cost)
        db.session.add(row)
        db.session.flush()
        if item['disposition'] == 'restock':
            move(stocks[line.product_id], item['quantity'] * line.conversion, cost,
                 'return', data['reason'], location=sale_location(line.mode) if sale.transaction_type else 'wholesale', return_line_id=row.id)
    for item in data['refunds']:
        payment = db.session.get(Payment, item['payment_id'])
        if not payment or payment.sale_id != sale.id:
            raise BadRequest('Refund must reference an original payment.')
        refunded = db.session.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(Refund.payment_id == payment.id))
        if refunded + item['amount'] > payment.amount:
            raise Conflict('Refund exceeds original payment allocation.')
        if payment.method != 'cash' and not item['reference']:
            raise BadRequest('External refunds require an independently verified refund reference.')
        row = Refund(return_id=returned.id, **item)
        db.session.add(row)
        db.session.flush()
        if payment.method in ('cash', 'external_mobile'):
            db.session.add(CashMovement(session_id=register.id, refund_id=row.id, method=payment.method, amount=-row.amount,
                reason=data['reason'], user_id=g.user.id))
    audit('sale.returned', 'return', returned.id, {'sale_id': sale.id})
    return returned
