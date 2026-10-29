"""Origin boundary for the dedicated loopback listener behind Tailscale Funnel.

Never trust forwarded client-IP headers from public callers. Login throttling on
this listener intentionally uses one shared proxy-IP bucket.
"""
import re
from urllib.parse import urlsplit
from flask import request, abort


def validate_origin(value):
    if not isinstance(value, str):
        raise ValueError('Remote origin must be an HTTPS Tailscale address.')
    url = urlsplit(value)
    if (url.scheme != 'https' or not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net', url.netloc)
            or url.path or url.query or url.fragment):
        raise ValueError('Use the exact https://machine.tailnet.ts.net address, without a path or port.')
    return value


def protect_remote(app):
    origin = app.config.get('REMOTE_ORIGIN')
    if not origin:
        return
    validate_origin(origin)
    if not app.config['JWT_COOKIE_SECURE'] or not app.config['JWT_COOKIE_CSRF_PROTECT']:
        raise ValueError('Remote access requires Secure cookies and CSRF protection.')
    host = urlsplit(origin).netloc

    @app.before_request
    def check_remote_origin():
        # Host is preserved by the HTTPS proxy; arbitrary forwarded headers do not
        # influence routing, cookie security, authorization or rate-limit identity.
        if request.host != host:
            abort(400, 'Unexpected remote host.')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if request.headers.get('Origin') != origin:
                abort(403, 'Remote requests must originate from this HTTPS workspace.')
            if request.mimetype != 'application/json':
                abort(415, 'Use application/json.')

    @app.after_request
    def secure_transport(response):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response
