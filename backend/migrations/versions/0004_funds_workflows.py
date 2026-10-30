"""Track supplier/cash payments without assigning payment status to historical orders."""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('purchase_line',sa.Column('pack_size_snapshot',sa.Numeric(18,3)))
    op.add_column('purchase_line',sa.Column('purchase_unit',sa.String(10)))
    op.add_column('purchase',sa.Column('payments_tracked',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('cash_movement',sa.Column('kind',sa.String(30),nullable=False,server_default='settlement'))
    op.add_column('cash_movement',sa.Column('reference',sa.String(120)))
    # SQLite table rebuilding would drop immutable-history triggers. Add nullable
    # reference columns directly, preserving every existing row and trigger.
    if op.get_bind().dialect.name=='sqlite':
        op.execute('ALTER TABLE cash_movement ADD COLUMN purchase_id INTEGER REFERENCES purchase(id)')
        op.execute('ALTER TABLE cash_movement ADD COLUMN reverses_id INTEGER REFERENCES cash_movement(id)')
    else:
        op.add_column('cash_movement',sa.Column('purchase_id',sa.Integer()))
        op.add_column('cash_movement',sa.Column('reverses_id',sa.Integer()))
        op.create_foreign_key('funds_purchase','cash_movement','purchase',['purchase_id'],['id'])
        op.create_foreign_key('funds_reversal','cash_movement','cash_movement',['reverses_id'],['id'])
    op.create_index('unique_funds_reversal','cash_movement',['reverses_id'],unique=True)
    op.create_index('unique_cash_movement_reference','cash_movement',['method','reference'],unique=True)


def downgrade():
    raise RuntimeError('Payment history cannot be discarded. Restore a pre-upgrade backup instead.')
