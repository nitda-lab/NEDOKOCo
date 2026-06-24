from db.engine import _normalize_url


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
