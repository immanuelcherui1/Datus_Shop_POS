import click
from flask import g
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import Branch, User, Product, Stock


def register_cli(app):
    @app.cli.command('create-owner')
    @click.option('--username', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_owner(username, password):
        """Bootstrap one installation. Passwords are prompted, never hardcoded."""
        if len(password) < 12:
            raise click.ClickException('Use a password of at least 12 characters.')
        if db.session.scalar(select(User.id).limit(1)):
            raise click.ClickException('Installation already initialized. Use Users to add accounts.')
        branch = Branch(name='Main shop')
        db.session.add(branch)
        db.session.flush()
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role='owner', branch_id=branch.id))
        db.session.commit()
        click.echo('Owner created. No default credentials were installed.')

    @app.cli.command('reset-password')
    @click.option('--username', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def reset_password(username, password):
        """Local administrator recovery; invalidates all existing sessions for that user."""
        user = db.session.scalar(select(User).where(User.username == username))
        if not user or len(password) < 12:
            raise click.ClickException('Unknown user or password shorter than 12 characters.')
        user.password_hash = generate_password_hash(password)
        user.token_version += 1
        g.user = user
        from .services import audit
        audit('user.password_reset_local', 'user', user.id)
        db.session.commit()
        click.echo('Password reset and existing sessions invalidated.')

    @app.cli.command('seed-demo')
    def seed():
        """Insert sample catalogue only. Receive stock through the actual inventory workflow."""
        owner = db.session.scalar(select(User).where(User.role == 'owner'))
        if not owner:
            raise click.ClickException('Create an owner first.')
        if db.session.scalar(select(Product.id).limit(1)):
            raise click.ClickException('Seed is allowed only on an empty catalogue.')
        g.user = owner
        from .services import audit
        for sku, name, price, pack, wholesale in [('DT-001', 'Premium maize flour 2kg', '180', '12', '2040'),
            ('DT-002', 'White sugar 1kg', '160', '20', '3000'), ('DT-003', 'Cooking oil 1L', '280', '12', '3120'),
            ('DT-004', 'Laundry soap 800g', '150', '12', '1680')]:
            p = Product(sku=sku, name=name, category='Essentials', retail_price=price,
                wholesale_price=wholesale, pack_size=pack, tax_rate=0, reorder_level=10)
            db.session.add(p)
            db.session.flush()
            db.session.add(Stock(product_id=p.id, branch_id=owner.branch_id, quantity=0, value=0))
            audit('product.seeded', 'product', p.id)
        db.session.commit()
        click.echo('Sample products created with zero stock. Tax rates are examples, not tax advice.')

    @app.cli.command('reconcile')
    def reconcile():
        from .api import reconciliation
        import json
        failures = False
        for branch in db.session.scalars(select(Branch)):
            result = reconciliation(branch.id)
            click.echo(json.dumps({'branch_id': branch.id, **result}))
            failures |= not result['ok']
        if failures:
            raise click.ClickException('Ledger discrepancy detected. Investigate before further posting.')
