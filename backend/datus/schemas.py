"""Reject unknown fields and reject imprecise/oversized financial inputs."""
from decimal import Decimal, InvalidOperation
from marshmallow import Schema, fields, validate, ValidationError, validates_schema


class Exact(fields.Field):
    def __init__(self, scale=2, minimum='0', maximum='1000000000', **kwargs):
        super().__init__(**kwargs)
        self.scale, self.minimum, self.maximum = scale, Decimal(minimum), Decimal(maximum)

    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, str):
            raise ValidationError('Send exact decimal values as strings.')
        try:
            result = Decimal(value)
            if not result.is_finite() or not self.minimum <= result <= self.maximum:
                raise ValueError()
            if result != result.quantize(Decimal(10) ** -self.scale):
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise ValidationError(f'Expected a value from {self.minimum} to {self.maximum}, at most {self.scale} decimal places.')
        return result


def text(maximum=160, **kw):
    return fields.String(validate=validate.Length(min=1, max=maximum), **kw)


class LoginSchema(Schema):
    username = text(80, required=True)
    password = text(200, required=True)


class UserSchema(Schema):
    username = text(80, required=True)
    password = fields.String(required=True, validate=validate.Length(min=12, max=200))
    role = fields.String(required=True, validate=validate.OneOf(['owner', 'manager', 'cashier', 'inventory', 'accountant']))


class ProductSchema(Schema):
    sku = fields.String(required=True, validate=validate.Regexp(r'^[A-Za-z0-9._-]{1,60}$'))
    barcode = fields.String(load_default=None, allow_none=True, validate=validate.Length(min=1, max=80))
    name = text(required=True)
    category = text(80, load_default='General')
    unit = text(30, load_default='piece')
    packaging_unit = text(30, load_default='pack')
    expiry_date = fields.Date(load_default=None, allow_none=True)
    retail_price = Exact(required=True)
    wholesale_price = Exact(required=True)
    pack_size = Exact(0, '1', required=True)
    tax_rate = Exact(4, maximum='1', load_default=Decimal('0'))
    reorder_level = Exact(0, load_default=Decimal('5'))
    active = fields.Boolean(load_default=True)


class PurchaseLineSchema(Schema):
    purchase_unit = fields.String(load_default='unit', validate=validate.OneOf(['unit', 'pack']))
    product_id = fields.Integer(required=True, strict=True)
    quantity = Exact(0, '1', required=True)
    unit_cost = Exact(6, required=True)


class PurchaseSchema(Schema):
    status = fields.String(load_default='ordered', validate=validate.OneOf(['draft', 'ordered']))
    supplier_id = fields.Integer(required=True, strict=True)
    lines = fields.List(fields.Nested(PurchaseLineSchema), required=True, validate=validate.Length(min=1, max=100))


class ReceiveLineSchema(Schema):
    unit_cost = Exact(6, load_default=None, allow_none=True)
    line_id = fields.Integer(required=True, strict=True)
    quantity = Exact(0, '1', required=True)


class ReceiveSchema(Schema):
    lines = fields.List(fields.Nested(ReceiveLineSchema), required=True, validate=validate.Length(min=1, max=100))


class CartLineSchema(Schema):
    product_id = fields.Integer(required=True, strict=True)
    quantity = Exact(3, '0.001', required=True)
    mode = fields.String(required=True, validate=validate.OneOf(['retail', 'wholesale', 'retail_pack', 'wholesale_unit']))
    discount = Exact(load_default=Decimal('0'))


    @validates_schema
    def whole_wholesale_packs(self, data, **kwargs):
        if data['mode'] != 'retail' and data['quantity'] != data['quantity'].to_integral_value():
            raise ValidationError({'quantity': ['Wholesale quantities and retail packs must be whole numbers.']})


class PaymentSchema(Schema):
    method = fields.String(required=True, validate=validate.OneOf(['cash', 'external_card', 'external_mobile', 'external_bank']))
    amount = Exact(minimum='0.01', required=True)
    reference = text(120, load_default=None, allow_none=True)


class QuoteSchema(Schema):
    customer = text(load_default='Walk-in customer')
    lines = fields.List(fields.Nested(CartLineSchema), required=True, validate=validate.Length(min=1, max=100))


class CheckoutSchema(QuoteSchema):
    payments = fields.List(fields.Nested(PaymentSchema), required=True, validate=validate.Length(min=1, max=10))


class AdjustmentSchema(Schema):
    location = fields.String(load_default='wholesale', validate=validate.OneOf(['wholesale', 'retail']))
    product_id = fields.Integer(required=True, strict=True)
    quantity = Exact(0, '-1000000000', required=True)
    unit_cost = Exact(6, load_default=Decimal('0'))
    reason = fields.String(required=True, validate=validate.Length(min=5, max=500))


class SupplierSchema(Schema):
    email = fields.String(load_default='', validate=validate.Length(max=160))
    address = fields.String(load_default='', validate=validate.Length(max=500))
    details = fields.String(load_default='', validate=validate.Length(max=500))
    name = text(required=True)
    phone = fields.String(load_default='', validate=validate.Length(max=40))


class OpenSessionSchema(Schema):
    opening_mpesa = Exact(load_default=Decimal('0'))
    opening = Exact(required=True)


class CloseSessionSchema(Schema):
    counted_mpesa = Exact(load_default=Decimal('0'))
    counted = Exact(required=True)
    notes = fields.String(load_default='', validate=validate.Length(max=500))


class ReturnLineSchema(Schema):
    line_id = fields.Integer(required=True, strict=True)
    quantity = Exact(3, '0.001', required=True)
    disposition = fields.String(required=True, validate=validate.OneOf(['restock', 'damaged']))


class RefundSchema(Schema):
    payment_id = fields.Integer(required=True, strict=True)
    amount = Exact(minimum='0.01', required=True)
    reference = text(120, load_default=None, allow_none=True)


class ReturnSchema(Schema):
    reason = fields.String(required=True, validate=validate.Length(min=5, max=500))
    lines = fields.List(fields.Nested(ReturnLineSchema), required=True, validate=validate.Length(min=1, max=100))
    refunds = fields.List(fields.Nested(RefundSchema), required=True, validate=validate.Length(min=1, max=10))


class TransferSchema(Schema):
    product_id = fields.Integer(required=True, strict=True)
    quantity = Exact(0, '1', required=True)
    unit = fields.String(load_default='unit', validate=validate.OneOf(['unit', 'pack']))
    reason = fields.String(required=True, validate=validate.Length(min=5, max=500))


class CatalogueSchema(Schema):
    kind = fields.String(required=True, validate=validate.OneOf(['category', 'unit']))
    name = text(80, required=True)
