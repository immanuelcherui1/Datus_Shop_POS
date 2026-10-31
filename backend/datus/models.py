"""Persistent facts and derived stock. See docs/INVENTORY.md before changing posting logic."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, UniqueConstraint, event
from .extensions import db


def now():
    return datetime.now(timezone.utc)


class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    token_version = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("role IN ('owner','manager','cashier','inventory','accountant')"),)


class Product(db.Model):
    packages = db.Column(db.JSON)
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(60), unique=True, nullable=False)
    barcode = db.Column(db.String(80), unique=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False, default='General')
    unit = db.Column(db.String(30), nullable=False, default='piece')
    packaging_unit = db.Column(db.String(30), nullable=False, default='pack')
    expiry_date = db.Column(db.Date)
    retail_price = db.Column(db.Numeric(18, 2), nullable=False)
    wholesale_price = db.Column(db.Numeric(18, 2), nullable=False)
    pack_size = db.Column(db.Numeric(18, 3), nullable=False, default=1)
    tax_rate = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    reorder_level = db.Column(db.Numeric(18, 3), nullable=False, default=5)
    active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint('retail_price >= 0 AND wholesale_price >= 0'),
                      CheckConstraint('pack_size >= 1 AND reorder_level >= 0'),
                      CheckConstraint('tax_rate >= 0 AND tax_rate <= 1'))


class Stock(db.Model):
    """A cache, always updated atomically with Movement. Never edit it directly."""
    product_id = db.Column(db.ForeignKey('product.id'), primary_key=True)
    branch_id = db.Column(db.ForeignKey('branch.id'), primary_key=True)
    quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    value = db.Column(db.Numeric(18, 6), nullable=False, default=0)
    retail_quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    retail_value = db.Column(db.Numeric(18, 6), nullable=False, default=0)
    __table_args__ = (CheckConstraint('quantity >= 0 AND value >= 0'),
        CheckConstraint('retail_quantity >= 0 AND retail_quantity <= quantity AND retail_value >= 0 AND retail_value <= value'),)


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False, default='')
    email = db.Column(db.String(160), nullable=False, default='')
    address = db.Column(db.String(500), nullable=False, default='')
    details = db.Column(db.String(500), nullable=False, default='')


class CatalogueOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    __table_args__ = (UniqueConstraint('kind', 'name'),)


class Purchase(db.Model):
    payments_tracked = db.Column(db.Boolean, nullable=False, default=True, server_default=db.false())
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.ForeignKey('supplier.id'), nullable=False)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    status = db.Column(db.String(20), nullable=False, default='ordered')
    lines = db.relationship('PurchaseLine', backref='purchase', lazy='selectin')


class PurchaseLine(db.Model):
    packaging_key = db.Column(db.String(30))
    packaging_snapshot = db.Column(db.JSON)
    pack_size_snapshot = db.Column(db.Numeric(18,3))
    purchase_unit = db.Column(db.String(10))
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.ForeignKey('purchase.id'), nullable=False)
    product_id = db.Column(db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    description = db.Column(db.String(160))
    unit = db.Column(db.String(30))
    conversion = db.Column(db.Numeric(18, 3), nullable=False, default=1)
    ordered_quantity = db.Column(db.Numeric(18, 3))
    ordered_unit_cost = db.Column(db.Numeric(18, 6))
    received = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(18, 6), nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0 AND received >= 0 AND received <= quantity AND unit_cost >= 0'),)


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.ForeignKey('purchase.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class CashSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    closed_at = db.Column(db.DateTime(timezone=True))
    opening = db.Column(db.Numeric(18, 2), nullable=False)
    counted = db.Column(db.Numeric(18, 2))
    expected = db.Column(db.Numeric(18, 2))
    notes = db.Column(db.String(500))
    opening_mpesa = db.Column(db.Numeric(18, 2), nullable=True, default=0)
    counted_mpesa = db.Column(db.Numeric(18, 2))
    expected_mpesa = db.Column(db.Numeric(18, 2))
    closed_by_id = db.Column(db.ForeignKey('user.id'))
    __table_args__ = (CheckConstraint('opening >= 0 AND (counted IS NULL OR counted >= 0)'),
        db.Index('one_open_register_per_branch', 'branch_id', unique=True,
                 postgresql_where=db.text('closed_at IS NULL'), sqlite_where=db.text('closed_at IS NULL')))


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(40), unique=True, nullable=False)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.ForeignKey('cash_session.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, index=True)
    currency = db.Column(db.String(3), nullable=False)
    business_name = db.Column(db.String(160), nullable=False)
    transaction_type = db.Column(db.String(20))
    served_by = db.Column(db.String(80))
    customer = db.Column(db.String(160), nullable=False, default='Walk-in customer')
    subtotal = db.Column(db.Numeric(18, 2), nullable=False)
    tax = db.Column(db.Numeric(18, 2), nullable=False)
    total = db.Column(db.Numeric(18, 2), nullable=False)
    cost = db.Column(db.Numeric(18, 6), nullable=False)
    lines = db.relationship('SaleLine', backref='sale', lazy='selectin')
    payments = db.relationship('Payment', backref='sale', lazy='selectin')
    __table_args__ = (CheckConstraint('total = subtotal + tax AND subtotal >= 0 AND tax >= 0'),)


class SaleLine(db.Model):
    packaging_key = db.Column(db.String(30))
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.ForeignKey('product.id'), nullable=False)
    sku = db.Column(db.String(60), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    conversion = db.Column(db.Numeric(18, 3), nullable=False)
    base_quantity = db.Column(db.Numeric(18, 3), nullable=False)
    unit_price = db.Column(db.Numeric(18, 6), nullable=False)
    discount = db.Column(db.Numeric(18, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(7, 4), nullable=False)
    subtotal = db.Column(db.Numeric(18, 2), nullable=False)
    tax = db.Column(db.Numeric(18, 2), nullable=False)
    cost = db.Column(db.Numeric(18, 6), nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0 AND base_quantity > 0 AND conversion > 0'),
                     CheckConstraint('discount >= 0 AND subtotal >= 0 AND tax >= 0 AND cost >= 0'))


class Payment(db.Model):
    """Recorded settlement, not an unverified provider attempt. One sale allocation per row."""
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.ForeignKey('sale.id'), nullable=False)
    method = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    reference = db.Column(db.String(120))
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (CheckConstraint('amount > 0'),
        CheckConstraint("method IN ('cash','external_card','external_mobile','external_bank')"),
        UniqueConstraint('method', 'reference', name='unique_external_payment_reference'))


class Return(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.ForeignKey('sale.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    reason = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    tax = db.Column(db.Numeric(18, 2), nullable=False)
    cost = db.Column(db.Numeric(18, 6), nullable=False)
    lines = db.relationship('ReturnLine', lazy='selectin')


class ReturnLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.ForeignKey('return.id'), nullable=False)
    sale_line_id = db.Column(db.ForeignKey('sale_line.id'), nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    disposition = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    tax = db.Column(db.Numeric(18, 2), nullable=False)
    cost = db.Column(db.Numeric(18, 6), nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0'), CheckConstraint("disposition IN ('restock','damaged')"))


class Refund(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.ForeignKey('return.id'), nullable=False)
    payment_id = db.Column(db.ForeignKey('payment.id'), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    reference = db.Column(db.String(120), unique=True)
    __table_args__ = (CheckConstraint('amount > 0'),)


class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.ForeignKey('product.id'), nullable=False)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(20), nullable=False, default='wholesale')
    transfer_reference = db.Column(db.String(40))
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    value = db.Column(db.Numeric(18, 6), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    reason = db.Column(db.String(500), nullable=False)
    sale_line_id = db.Column(db.ForeignKey('sale_line.id'))
    receipt_id = db.Column(db.ForeignKey('receipt.id'))
    return_line_id = db.Column(db.ForeignKey('return_line.id'))
    __table_args__ = (CheckConstraint('quantity != 0'),
                     db.Index('movement_balance_lookup', 'branch_id', 'product_id'))


class CashMovement(db.Model):
    kind = db.Column(db.String(30), nullable=False, default='settlement', server_default='settlement')
    purchase_id = db.Column(db.ForeignKey('purchase.id'))
    reverses_id = db.Column(db.ForeignKey('cash_movement.id'), unique=True)
    reference = db.Column(db.String(120))
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.ForeignKey('cash_session.id'), nullable=False)
    method = db.Column(db.String(20), nullable=False, default='cash')
    payment_id = db.Column(db.ForeignKey('payment.id'), unique=True)
    refund_id = db.Column(db.ForeignKey('refund.id'), unique=True)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (CheckConstraint('amount != 0'), UniqueConstraint('method','reference',name='unique_cash_movement_reference'))


class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    branch_id = db.Column(db.ForeignKey('branch.id'), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    entity = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class Idempotency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    scope = db.Column(db.String(80), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    response = db.Column(db.JSON)
    __table_args__ = (UniqueConstraint('user_id', 'scope', 'key', name='unique_retry'),)


# ORM protection helps developers; migration-installed triggers also reject raw SQL changes.
IMMUTABLE = (Movement, Sale, SaleLine, Payment, Return, ReturnLine, Refund, Receipt, CashMovement, Audit)


def deny_change(mapper, connection, target):
    raise ValueError('Posted history is immutable; use a compensating transaction.')


for model in IMMUTABLE:
    event.listen(model, 'before_update', deny_change)
    event.listen(model, 'before_delete', deny_change)
