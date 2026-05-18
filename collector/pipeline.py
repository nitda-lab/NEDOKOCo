import asyncio

from collector.ai_scorer import score_worlds
from collector.vrc_client import search_worlds
from db.engine import AsyncSessionLocal
from db.repository import get_unscored_worlds, save_ai_scores, upsert_world


async def run_collection() -> tuple[int, int]:
    """
    Returns (total_new, qualified) where qualified = is_japanese AND sleep_score >= 6.
    """
    worlds = await asyncio.to_thread(search_worlds)

    new_count = 0
    for data in worlds:
        async with AsyncSessionLocal() as session:
            _, created = await upsert_world(session, data)
            if created:
                new_count += 1

    async with AsyncSessionLocal() as session:
        unscored = await get_unscored_worlds(session)

    if unscored:
        scores = await asyncio.to_thread(score_worlds, unscored)
        async with AsyncSessionLocal() as session:
            await save_ai_scores(session, scores)

    qualified = sum(
        1 for s in scores
        if s.get("is_japanese") and s.get("sleep_score", 0) >= 6
    ) if unscored else 0

    return new_count, qualified
