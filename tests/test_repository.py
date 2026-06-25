from db.repository import (
    count_qualified,
    count_unscored,
    count_worlds,
    get_random_worlds,
    list_qualified_worlds,
    save_ai_scores,
    upsert_world,
)


def _world(i: int) -> dict:
    return {
        "world_id": f"wrld_{i}",
        "name": f"world {i}",
        "author_name": "author",
        "vrc_url": f"https://vrchat.com/home/world/wrld_{i}",
    }


async def test_counts_and_qualified_listing(session):
    for i in range(3):
        await upsert_world(session, _world(i))
    assert await count_worlds(session) == 3
    assert await count_unscored(session) == 3
    assert await count_qualified(session) == 0

    await save_ai_scores(session, [
        {"world_id": "wrld_0", "is_japanese": True, "sleep_score": 8},
        {"world_id": "wrld_1", "is_japanese": True, "sleep_score": 3},
        {"world_id": "wrld_2", "is_japanese": False, "sleep_score": 9},
    ])
    assert await count_unscored(session) == 0
    assert await count_qualified(session) == 1

    qualified = await list_qualified_worlds(session, limit=10, offset=0)
    assert [w.world_id for w in qualified] == ["wrld_0"]


async def test_get_random_worlds_respects_threshold(session):
    await upsert_world(session, _world(0))
    await save_ai_scores(session, [{"world_id": "wrld_0", "is_japanese": True, "sleep_score": 8}])
    worlds = await get_random_worlds(session, count=5)
    assert len(worlds) == 1


async def test_upsert_world_saves_metrics(session):
    from datetime import datetime

    from sqlalchemy import select

    from db.models import World

    await upsert_world(session, {
        "world_id": "wrld_m", "name": "n", "author_name": "a",
        "vrc_url": "https://vrchat.com/home/world/wrld_m",
        "vrc_updated_at": datetime(2026, 6, 3), "favorites": 99, "popularity": 12,
    })
    row = (await session.execute(select(World).where(World.world_id == "wrld_m"))).scalar_one()
    assert row.favorites == 99
    assert row.popularity == 12
    assert row.vrc_updated_at.day == 3
