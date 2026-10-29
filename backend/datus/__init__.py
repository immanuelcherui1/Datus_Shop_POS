import os
import logging
from datetime import timedelta
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import event
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash
from .extensions import db, migrate, jwt, limiter
from .paths import resource_root, data_root

ROOT = resource_root()


def create_app(config=None):
    load_dotenv(data_root() / '.env')
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///datus.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.getenv('SECRET_KEY'), JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY'),
        JWT_TOKEN_LOCATION=['cookies'], JWT_COOKIE_CSRF_PROTECT=True,
        JWT_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
        JWT_COOKIE_SAMESITE='Strict', JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=8),
        MAX_CONTENT_LENGTH=128 * 1024, BUSINESS_NAME=os.getenv('BUSINESS_NAME', 'DATUS'),
        CURRENCY=os.getenv('CURRENCY', 'KES'), BUSINESS_TIMEZONE=os.getenv('BUSINESS_TIMEZONE', 'Africa/Nairobi'),
        RATELIMIT_STORAGE_URI='memory://', DUMMY_PASSWORD_HASH=generate_password_hash(os.urandom(32).hex()))
    if config:
        app.config.update(config)
    for name in ('SECRET_KEY', 'JWT_SECRET_KEY'):
        value = app.config[name]
        if not value or len(value) < 32 or 'GENERATE_' in value:
            raise RuntimeError(f'{name} must be a generated secret of at least 32 characters.')
    from .remote import protect_remote
    protect_remote(app)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    db.init_app(app)
    with app.app_context():
        if db.engine.dialect.name == 'sqlite':
            @event.listens_for(db.engine, 'connect')
            def sqlite_foreign_keys(connection, _):
                connection.execute('PRAGMA foreign_keys=ON')
    migrate.init_app(app, db, directory=str(ROOT / 'backend' / 'migrations'))
    jwt.init_app(app)
    limiter.init_app(app)
    from .api import api
    app.register_blueprint(api)
    from .cli import register_cli
    register_cli(app)

    @app.errorhandler(ValidationError)
    def validation(error):
        db.session.rollback()
        return jsonify(error='Validation failed.', fields=error.messages), 400

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error='A unique value or database constraint was violated. Check SKU, barcode, payment reference, or open register.'), 409

    @app.errorhandler(OperationalError)
    def unavailable(error):
        db.session.rollback()
        app.logger.error('Database operation unavailable (%s)', type(error).__name__)
        return jsonify(error='Database temporarily unavailable. Retry with the same operation key.'), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        db.session.rollback()
        # Never log SQL parameters, credentials, or complete request bodies.
        app.logger.error('Unhandled request error (%s)', type(error).__name__)
        return jsonify(error='The operation failed and was rolled back.'), 500

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        if response.mimetype == 'application/json':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/health')
    def health():
        db.session.execute(db.text('SELECT 1'))
        return jsonify(status='ok', application='DATUS', remote_access=bool(app.config.get('REMOTE_ORIGIN')))

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        if path.startswith('api/'):
            from werkzeug.exceptions import NotFound
            raise NotFound()
        dist = ROOT / 'frontend' / 'dist'
        return send_from_directory(dist, path if (dist / path).is_file() else 'index.html')

    return app
