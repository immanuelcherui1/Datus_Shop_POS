"""Named packaging options share one base-unit inventory; history stores snapshots."""
from decimal import Decimal, ROUND_HALF_UP
from werkzeug.exceptions import BadRequest, Conflict


def options(product):
    if product.packages:
        return product.packages
    return [dict(key='unit', name=product.unit, conversion='1',
                 wholesale_price=str((product.wholesale_price / product.pack_size).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)),
                 retail_price=str(product.retail_price)),
            dict(key='pack', name=product.packaging_unit, conversion=str(product.pack_size),
                 wholesale_price=str(product.wholesale_price), retail_price=str(product.retail_price * product.pack_size))]


def resolve(product, key):
    for option in options(product):
        if option['key'] == key:
            return option
    raise BadRequest('This packaging option no longer exists. Refresh the product and select a unit.')


def selected(product, data, unit_field='unit'):
    return resolve(product, data.get('packaging_key') or data.get(unit_field, 'unit'))


def normalize(data, previous=None, used=False):
    """Stable keys and factors prevent existing orders/carts from changing meaning."""
    if 'packages' not in data:
        return
    rows = data['packages']
    if not rows:
        if previous and previous.packages:
            raise BadRequest('Keep packaging options; clear a selling price to disable that channel.')
        data['packages'] = None
        return
    keys = [p['key'] for p in rows]
    names = [p['name'].strip().casefold() for p in rows]
    if len(keys) != len(set(keys)) or len(names) != len(set(names)) or any(not n for n in names):
        raise BadRequest('Packaging keys and names must be unique and nonempty.')
    by_key = {p['key']: p for p in rows}
    if 'unit' not in by_key or 'pack' not in by_key:
        raise BadRequest('Keep the base unit (unit) and primary packaging unit (pack).')
    if by_key['unit']['conversion'] != 1 or by_key['pack']['conversion'] != data['pack_size']:
        raise BadRequest('Base conversion must be 1; primary pack conversion must match pack size.')
    if by_key['unit']['name'].strip() != data['unit'].strip() or by_key['pack']['name'].strip() != data['packaging_unit'].strip():
        raise BadRequest('Base and primary pack names must match the product unit labels.')
    if used and previous:
        for old in options(previous):
            new = by_key.get(old['key'])
            if not new or Decimal(old['conversion']) != new['conversion'] or old['name'] != new['name'].strip():
                raise Conflict('Existing packaging names and conversions are fixed after stock/orders exist. Add a new option instead.')
    data['retail_price'] = by_key['unit']['retail_price'] or Decimal(0)
    data['wholesale_price'] = by_key['pack']['wholesale_price'] or Decimal(0)
    data['packages'] = [{k: (str(v) if isinstance(v, Decimal) else v.strip() if isinstance(v, str) else v)
                         for k, v in row.items()} for row in rows]
