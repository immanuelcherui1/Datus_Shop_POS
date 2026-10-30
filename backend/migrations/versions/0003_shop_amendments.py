"""Separate stock allocation without rewriting immutable historical transactions.

Existing stock starts in wholesale. Historical movements retain a legacy label;
the reconciliation combines these into the wholesale opening balance.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM cash_session WHERE closed_at IS NULL')).scalar():
        raise RuntimeError('Close all trading sessions in the previous DATUS version and take a backup before upgrading to stock allocations.')
    additions = {
        'product': [sa.Column('packaging_unit', sa.String(30), nullable=False, server_default='pack'), sa.Column('expiry_date', sa.Date())],
        'stock': [sa.Column('retail_quantity', sa.Numeric(18,3), nullable=False, server_default='0'), sa.Column('retail_value', sa.Numeric(18,6), nullable=False, server_default='0')],
        'supplier': [sa.Column(k, sa.String(n), nullable=False, server_default='') for k,n in [('email',160),('address',500),('details',500)]],
        'purchase_line': [sa.Column('description',sa.String(160)),sa.Column('unit',sa.String(30)),sa.Column('conversion',sa.Numeric(18,3),nullable=False,server_default='1'),sa.Column('ordered_quantity',sa.Numeric(18,3)),sa.Column('ordered_unit_cost',sa.Numeric(18,6))],
        'cash_session': [sa.Column('opening_mpesa',sa.Numeric(18,2),nullable=True),sa.Column('counted_mpesa',sa.Numeric(18,2)),sa.Column('expected_mpesa',sa.Numeric(18,2)),sa.Column('closed_by_id',sa.Integer())],
        'sale': [sa.Column('transaction_type',sa.String(20)),sa.Column('served_by',sa.String(80))],
        'movement': [sa.Column('location',sa.String(20),nullable=False,server_default='legacy'),sa.Column('transfer_reference',sa.String(40))],
        'cash_movement': [sa.Column('method',sa.String(20),nullable=False,server_default='cash')],
    }
    for table, columns in additions.items():
        for column in columns:
            op.add_column(table, column)
    op.create_table('catalogue_option',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('kind',sa.String(20),nullable=False),sa.Column('name',sa.String(80),nullable=False),sa.UniqueConstraint('kind','name'))
    op.execute("INSERT INTO catalogue_option (kind,name) SELECT 'category',category FROM product GROUP BY category")
    op.execute("INSERT INTO catalogue_option (kind,name) SELECT 'unit',unit FROM product GROUP BY unit")
    if op.get_bind().dialect.name == 'postgresql':
        op.alter_column('sale_line','unit_price',type_=sa.Numeric(18,6),existing_type=sa.Numeric(18,2))
        op.create_foreign_key('session_closed_by','cash_session','user',['closed_by_id'],['id'])
        op.create_check_constraint('stock_allocation_valid','stock','retail_quantity >= 0 AND retail_quantity <= quantity AND retail_value >= 0 AND retail_value <= value')
        op.create_check_constraint('mpesa_balances_valid','cash_session','opening_mpesa >= 0 AND (counted_mpesa IS NULL OR counted_mpesa >= 0)')
    else:
        # Avoid rebuilding immutable tables or dropping their triggers on SQLite.
        for action in ('INSERT','UPDATE'):
            op.execute(f"""CREATE TRIGGER stock_allocation_{action.lower()} BEFORE {action} ON stock
            WHEN NEW.retail_quantity < 0 OR NEW.retail_quantity > NEW.quantity OR NEW.retail_value < 0 OR NEW.retail_value > NEW.value
            BEGIN SELECT RAISE(ABORT, 'Invalid stock allocation'); END""")


def downgrade():
    raise RuntimeError('Allocation history cannot safely be downgraded. Restore a pre-upgrade backup instead.')
