from functools import wraps
from flask import g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.exceptions import Forbidden, Unauthorized
from .extensions import db
from .models import User

PERMISSIONS = {
    'owner': {'sell', 'catalog', 'purchase', 'adjust', 'report', 'refund', 'discount', 'users', 'external', 'audit', 'register'},
    'manager': {'sell', 'catalog', 'purchase', 'adjust', 'report', 'refund', 'discount', 'external', 'audit', 'register'},
    'cashier': {'sell', 'register'},
    'inventory': {'catalog', 'purchase', 'adjust'},
    'accountant': {'report', 'audit'},
}


def require(permission=None):
    def decorate(fn):
        @wraps(fn)
        @jwt_required()
        def wrapped(*args, **kwargs):
            user = db.session.get(User, int(get_jwt_identity()))
            if not user or not user.active or get_jwt().get('version') != user.token_version:
                raise Unauthorized('Session expired. Sign in again.')
            if permission and permission not in PERMISSIONS[user.role]:
                raise Forbidden('Your role cannot perform this action.')
            g.user = user
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def allowed(permission):
    if permission not in PERMISSIONS[g.user.role]:
        raise Forbidden(f'Permission required: {permission}.')


def scoped(record):
    # Return 404 for records in another branch to avoid disclosing their existence.
    from werkzeug.exceptions import NotFound
    if record is None or record.branch_id != g.user.branch_id:
        raise NotFound()
    return record
