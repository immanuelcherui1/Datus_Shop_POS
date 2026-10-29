import pytest
from datus import create_app
from datus.remote import validate_origin

ORIGIN = 'https://datus.test-tailnet.ts.net'


@pytest.mark.parametrize('origin', ['http://datus.test.ts.net', 'https://evil.example',
    'https://datus.test.ts.net/path', 'https://datus.test.ts.net:443', 'https://user@datus.test.ts.net',
    'https://datus.test.ts.net?query', 'https://datus.test.ts.net#fragment'])
def test_invalid_remote_origin(origin):
    with pytest.raises(ValueError):
        validate_origin(origin)


def remote_app(app, **overrides):
    return create_app({**app.config, 'REMOTE_ORIGIN': ORIGIN, 'JWT_COOKIE_SECURE': True,
        'JWT_COOKIE_CSRF_PROTECT': True, 'JWT_ACCESS_COOKIE_NAME': 'datus_remote_access', **overrides})


def test_remote_login_cookies_origin_and_csrf(app):
    remote = remote_app(app)
    client = remote.test_client()
    assert client.get('/api/health').status_code == 400
    assert client.get('/api/auth/me', base_url=ORIGIN).status_code == 401
    credentials = {'username': 'owner', 'password': 'test-only-password'}
    assert client.post('/api/auth/login', base_url=ORIGIN, json=credentials).status_code == 403
    assert client.post('/api/auth/login', base_url=ORIGIN, json=credentials,
        headers={'Origin': 'https://evil.example'}).status_code == 403
    response = client.post('/api/auth/login', base_url=ORIGIN, json=credentials, headers={'Origin': ORIGIN})
    assert response.status_code == 200
    cookie = next(x for x in response.headers.getlist('Set-Cookie') if x.startswith('datus_remote_access='))
    assert 'Secure;' in cookie and 'HttpOnly;' in cookie and 'SameSite=Strict' in cookie
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000'
    assert client.get('/api/auth/me', base_url=ORIGIN).status_code == 200
    assert client.post('/api/register/open', base_url=ORIGIN, json={'opening': '0'}, headers={'Origin': ORIGIN}).status_code == 401
    csrf = client.get_cookie('csrf_access_token', domain='datus.test-tailnet.ts.net').value
    assert client.post('/api/register/open', base_url=ORIGIN, json={'opening': '0'},
        headers={'Origin': ORIGIN, 'X-CSRF-TOKEN': csrf, 'Idempotency-Key': 'remote-test-1234'}).status_code == 200
    assert client.post('/api/auth/logout', base_url=ORIGIN, json={},
        headers={'Origin': ORIGIN, 'X-CSRF-TOKEN': csrf, 'Idempotency-Key': 'remote-test-1234'}).status_code == 200
    assert client.get('/api/auth/me', base_url=ORIGIN).status_code == 401
    assert not app.config.get('REMOTE_ORIGIN')
    assert not app.config['JWT_COOKIE_CSRF_PROTECT']  # local fixture was not mutated


def test_remote_refuses_insecure_config(app):
    with pytest.raises(ValueError):
        remote_app(app, JWT_COOKIE_SECURE=False)


def test_forwarded_headers_do_not_bypass_login_limit(app):
    remote = remote_app(app, RATELIMIT_ENABLED=True)
    client = remote.test_client()
    for n in range(10):
        response = client.post('/api/auth/login', base_url=ORIGIN,
            json={'username': 'unknown', 'password': 'incorrect'},
            headers={'Origin': ORIGIN, 'X-Forwarded-For': f'192.0.2.{n}'})
        assert response.status_code == 401
    assert client.post('/api/auth/login', base_url=ORIGIN,
        json={'username': 'unknown', 'password': 'incorrect'},
        headers={'Origin': ORIGIN, 'X-Forwarded-For': '198.51.100.1'}).status_code == 429
