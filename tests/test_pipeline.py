import collector.pipeline as pl


class _ctx:
    def __init__(self, s):
        self._s = s

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *a):
        return False


async def test_auth_required_when_no_cookie(session, monkeypatch):
    monkeypatch.setattr(pl, "_session", lambda: _ctx(session))

    async def _no_cookie():
        return None
    monkeypatch.setattr(pl, "get_active_cookie", _no_cookie)

    out = await pl.run_collection_chunk()
    assert out["status"] == "auth_required"


async def test_cursor_advances_and_wraps(session, monkeypatch):
    monkeypatch.setattr(pl, "_session", lambda: _ctx(session))
    monkeypatch.setattr(pl, "COLLECT_QUERY_BATCH", 2)
    monkeypatch.setattr(pl, "SEARCH_QUERIES", [{"search": "a"}, {"search": "b"}, {"search": "c"}])

    async def _cookie():
        return "authcookie_x"
    monkeypatch.setattr(pl, "get_active_cookie", _cookie)
    monkeypatch.setattr(pl, "_search", lambda cookie, queries: [])
    monkeypatch.setattr(pl, "_score", lambda unscored: [])

    out1 = await pl.run_collection_chunk()
    assert out1["cursor"] == 2
    out2 = await pl.run_collection_chunk()
    assert out2["cursor"] == 0
