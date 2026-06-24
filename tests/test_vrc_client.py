import collector.vrc_client as vc
from db.state import VRC_AUTH_COOKIE, VRC_PENDING_COOKIE, get_state, set_state


class _ctx:
    def __init__(self, s):
        self._s = s

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *a):
        return False


def test_extract_auth_cookie():
    headers = {"Set-Cookie": "auth=authcookie_abc; Path=/; HttpOnly"}
    assert vc._extract_auth_cookie(headers) == "authcookie_abc"
    assert vc._extract_auth_cookie({}) is None


def test_extract_twofactor_cookie():
    headers = {"Set-Cookie": "twoFactorAuth=tfa_xyz; Path=/"}
    assert vc._extract_twofactor_cookie(headers) == "tfa_xyz"
    assert vc._extract_twofactor_cookie({}) is None


async def test_login_saved_cookie_valid_returns_ok(session, monkeypatch):
    await set_state(session, VRC_AUTH_COOKIE, "authcookie_saved")

    monkeypatch.setattr(vc, "_session", lambda: _ctx(session))
    monkeypatch.setattr(vc, "_verify_cookie_sync", lambda cookie: True)

    assert await vc.login() == "ok"


async def test_login_requires_otp_saves_pending(session, monkeypatch):
    monkeypatch.setattr(vc, "_session", lambda: _ctx(session))
    monkeypatch.setattr(vc, "_verify_cookie_sync", lambda cookie: False)
    monkeypatch.setattr(vc, "_password_login_sync", lambda tfa: ("email_otp", "authcookie_pending", None))

    assert await vc.login() == "email_otp"
    assert await get_state(session, VRC_PENDING_COOKIE) == "authcookie_pending"
