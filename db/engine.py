import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base


def _normalize_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]
    if raw.startswith("postgresql+asyncpg://"):
        parts = urlsplit(raw)
        if parts.query:
            raw = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))
    return raw


def _connect_args(url: str) -> dict:
    if url.startswith("postgresql+asyncpg://"):
        return {"ssl": "require"}
    return {}


DATABASE_URL = _normalize_url(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/buisui.db"))

engine = create_async_engine(DATABASE_URL, connect_args=_connect_args(DATABASE_URL))
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
