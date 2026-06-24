import json
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import World

_SUGGEST_SCORE_MIN = 6


async def get_random_worlds(session: AsyncSession, count: int = 5, exclude_recent_hours: int = 3) -> list[World]:
    cutoff = datetime.utcnow() - timedelta(hours=exclude_recent_hours)
    stmt = (
        select(World)
        .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
        .where(World.ai_is_japanese == 1)
        .where((World.last_suggested_at == None) | (World.last_suggested_at < cutoff))  # noqa: E711
        .order_by(func.random())
        .limit(count)
    )
    result = await session.execute(stmt)
    worlds = list(result.scalars().all())

    if len(worlds) < count:
        existing_ids = {w.world_id for w in worlds}
        stmt_fallback = (
            select(World)
            .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
            .where(World.ai_is_japanese == 1)
            .where(World.world_id.not_in(existing_ids))
            .order_by(func.random())
            .limit(count - len(worlds))
        )
        result = await session.execute(stmt_fallback)
        worlds += list(result.scalars().all())

    return worlds


async def update_worlds_suggested(session: AsyncSession, world_ids: list[str]) -> None:
    for wid in world_ids:
        await session.execute(
            update(World)
            .where(World.world_id == wid)
            .values(last_suggested_at=datetime.utcnow(), suggest_count=World.suggest_count + 1)
        )
    await session.commit()


async def upsert_world(session: AsyncSession, data: dict, commit: bool = True) -> tuple[World, bool]:
    result = await session.execute(select(World).where(World.world_id == data["world_id"]))
    world = result.scalar_one_or_none()

    tags = data.get("tags")
    if isinstance(tags, list):
        tags = json.dumps(tags, ensure_ascii=False)

    if world:
        world.name = data["name"]
        world.author_name = data["author_name"]
        world.description = data.get("description")
        world.image_url = data.get("image_url")
        world.tags = tags
        world.capacity = data.get("capacity")
        world.fetched_at = datetime.utcnow()
        if commit:
            await session.commit()
        return world, False

    world = World(
        world_id=data["world_id"],
        name=data["name"],
        author_name=data["author_name"],
        description=data.get("description"),
        image_url=data.get("image_url"),
        tags=tags,
        capacity=data.get("capacity"),
        vrc_url=data["vrc_url"],
        fetched_at=datetime.utcnow(),
    )
    session.add(world)
    if commit:
        await session.commit()
    return world, True


async def get_unscored_worlds(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(World).where(World.ai_sleep_score == None)  # noqa: E711
    )
    worlds = result.scalars().all()
    return [
        {
            "world_id": w.world_id,
            "name": w.name,
            "author_name": w.author_name,
            "tags": w.tags,
        }
        for w in worlds
    ]


async def save_ai_scores(session: AsyncSession, scores: list[dict]) -> int:
    """scores: [{"world_id": ..., "is_japanese": bool, "sleep_score": int}]"""
    saved = 0
    for s in scores:
        await session.execute(
            update(World)
            .where(World.world_id == s["world_id"])
            .values(
                ai_sleep_score=s["sleep_score"],
                ai_is_japanese=1 if s["is_japanese"] else 0,
            )
        )
        saved += 1
    await session.commit()
    return saved


async def count_worlds(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(World))
    return int(result.scalar_one())


async def count_unscored(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(World).where(World.ai_sleep_score == None)  # noqa: E711
    )
    return int(result.scalar_one())


async def count_qualified(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(World)
        .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
        .where(World.ai_is_japanese == 1)
    )
    return int(result.scalar_one())


async def list_qualified_worlds(session: AsyncSession, limit: int, offset: int) -> list[World]:
    stmt = (
        select(World)
        .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
        .where(World.ai_is_japanese == 1)
        .order_by(World.fetched_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
