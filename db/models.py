from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    world_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    image_url: Mapped[str | None] = mapped_column(String)
    tags: Mapped[str | None] = mapped_column(String)  # JSON array string
    capacity: Mapped[int | None] = mapped_column(Integer)
    vrc_url: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_suggested_at: Mapped[datetime | None] = mapped_column(DateTime)
    suggest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_sleep_score: Mapped[int | None] = mapped_column(Integer)
    ai_is_japanese: Mapped[int | None] = mapped_column(Integer)  # 1=True / 0=False / NULL=未評価


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String)
