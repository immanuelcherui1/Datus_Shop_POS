"""Add optional packaging definitions and immutable transaction snapshots."""
from alembic import op
import sqlalchemy as sa
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product', sa.Column('packages', sa.JSON()))
    op.add_column('sale_line', sa.Column('packaging_key', sa.String(30)))
    op.add_column('purchase_line', sa.Column('packaging_key', sa.String(30)))
    op.add_column('purchase_line', sa.Column('packaging_snapshot', sa.JSON()))


def downgrade():
    raise RuntimeError('Packaging history cannot be discarded. Restore a pre-upgrade backup.')
