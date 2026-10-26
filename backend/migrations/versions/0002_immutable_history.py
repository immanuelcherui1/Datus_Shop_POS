"""Enforce immutable posted history at the database boundary.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None
TABLES = ('movement', 'sale', 'sale_line', 'payment', 'return', 'return_line',
          'refund', 'receipt', 'cash_movement', 'audit')


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        op.execute("""CREATE FUNCTION datus_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Posted history is immutable. Use a compensating transaction.';
        END; $$""")
        for table in TABLES:
            op.execute(f'CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON "{table}" '
                       'FOR EACH ROW EXECUTE FUNCTION datus_immutable()')
    elif dialect == 'sqlite':
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                op.execute(f'''CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON "{table}"
                    BEGIN SELECT RAISE(ABORT, 'Posted history is immutable'); END''')
    else:
        raise RuntimeError('DATUS supports PostgreSQL and SQLite only.')


def downgrade():
    dialect = op.get_bind().dialect.name
    for table in TABLES:
        if dialect == 'postgresql':
            op.execute(f'DROP TRIGGER immutable_{table} ON "{table}"')
        else:
            for action in ('update', 'delete'):
                op.execute(f'DROP TRIGGER immutable_{table}_{action}')
    if dialect == 'postgresql':
        op.execute('DROP FUNCTION datus_immutable()')
