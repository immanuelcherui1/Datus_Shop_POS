"""Posting services. Caller owns commit/rollback; no service commits halfway through."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from flask import current_app, g
from sqlalchemy import select, func
from werkzeug.exceptions import BadRequest, Conflict
from .extensions import db
from .models import (Product, Stock, Movement, Audit, Purchase, PurchaseLine, Receipt,
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


def move(stock, quantity, value, kind, reason, **links):
    if quantity == 0:
        raise BadRequest('Stock movement cannot be zero.')
    if stock.quantity + quantity < 0:
        raise Conflict('Insufficient stock. Refresh the cart and try again.')
    stock.quantity += quantity
    stock.value = valuation(stock.value + value)
    if stock.value < 0:
        raise Conflict('Inventory valuation would become negative.')
    db.session.add(Movement(product_id=stock.product_id, branch_id=stock.branch_id,
        user_id=g.user.id, quantity=quantity, value=value, kind=kind, reason=reason, **links))


def consume_value(stock, quantity):
    if quantity > stock.quantity or stock.quantity <= 0:
        raise Conflict('Insufficient stock.')
    # Consume the final residual value when the last unit leaves, preventing rounding dust.
    return stock.value if quantity == stock.quantity else valuation(stock.value * quantity / stock.quantity)


def quote(data):
    unique_lines(data['lines'], 'product_id')
    result = []
    for item in data['lines']:
        product = db.session.get(Product, item['product_id'])
        if not product or not product.active:
            raise BadRequest('Product is missing or inactive.')
        conversion = product.pack_size if item['mode'] == 'wholesale' else Decimal('1')
        price = product.wholesale_price if item['mode'] == 'wholesale' else product.retail_price
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
            unit=product.unit, mode=item['mode'], quantity=item['quantity'], conversion=conversion,
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
        subtotal=calculated['subtotal'], tax=calculated['tax'], total=calculated['total'], cost=ZERO)
    # Set cost before first flush: posted rows cannot be updated, even by this service.
    costs = [consume_value(stocks[line['product_id']], line['base_quantity']) for line in calculated['lines']]
    sale.cost = sum(costs, ZERO)
    db.session.add(sale)
    db.session.flush()
    for values, cost in zip(calculated['lines'], costs):
        line = SaleLine(sale_id=sale.id, cost=cost, **values)
        db.session.add(line)
        db.session.flush()
        move(stocks[line.product_id], -line.base_quantity, -cost, 'sale', sale.number, sale_line_id=line.id)
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
        if payment.method == 'cash':
            db.session.add(CashMovement(session_id=register.id, payment_id=payment.id,
                amount=payment.amount, reason=sale.number, user_id=g.user.id))
    audit('sale.posted', 'sale', sale.id, {'number': sale.number})
    # Optional fault injection used only by the test suite to prove full rollback.
    if current_app.testing and current_app.config.get('FAIL_CHECKOUT'):
        raise RuntimeError('Injected checkout failure')
    db.session.flush()
    return sale


def receive(purchase_id, data):
    purchase = scoped(db.session.scalar(select(Purchase).where(Purchase.id == purchase_id).with_for_update()))
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
        move(stocks[line.product_id], item['quantity'], valuation(item['quantity'] * line.unit_cost),
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
                 'return', data['reason'], return_line_id=row.id)
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
        if payment.method == 'cash':
            db.session.add(CashMovement(session_id=register.id, refund_id=row.id, amount=-row.amount,
                reason=data['reason'], user_id=g.user.id))
    audit('sale.returned', 'return', returned.id, {'sale_id': sale.id})
    return returned
