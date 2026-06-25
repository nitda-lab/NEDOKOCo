from db.engine import _connect_args, _normalize_url


def test_normalize_postgres_scheme():
    assert _normalize_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_postgresql_scheme():
    assert _normalize_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_strips_sslmode_query_for_asyncpg():
    out = _normalize_url("postgresql://u:p@h/db?sslmode=require")
    assert "sslmode" not in out
    assert out.startswith("postgresql+asyncpg://")


def test_normalize_passthrough_sqlite():
    assert _normalize_url("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"


async def test_init_db_runs_on_sqlite(monkeypatch, tmp_path):
    import db.engine as e
    from sqlalchemy.ext.asyncio import create_async_engine

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(e, "engine", test_engine)
    await e.init_db()
    await test_engine.dispose()


def test_connect_args_asyncpg_requires_ssl():
    assert _connect_args("postgresql+asyncpg://u:p@h/db") == {"ssl": "require"}


def test_connect_args_sqlite_empty():
    assert _connect_args("sqlite+aiosqlite:///x.db") == {}
