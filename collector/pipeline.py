import asyncio
import os
from datetime import datetime

from collector.ai_scorer import score_worlds
from collector.vrc_client import SEARCH_QUERIES, _search_worlds_with_cookie, get_active_cookie
from db.engine import AsyncSessionLocal
from db.repository import get_unscored_worlds, save_ai_scores, upsert_world
from db.state import COLLECT_CURSOR, LAST_COLLECT_AT, LAST_STATUS, get_state, set_state

COLLECT_QUERY_BATCH = int(os.getenv("COLLECT_QUERY_BATCH", "4"))


def _session():
    return AsyncSessionLocal()


def _search(cookie: str, queries: list[dict]) -> list[dict]:
    return _search_worlds_with_cookie(cookie, queries)


def _score(unscored: list[dict]) -> list[dict]:
    return score_worlds(unscored)


async def run_collection_chunk() -> dict:
    cookie = await get_active_cookie()
    if not cookie:
        async with _session() as s:
            await set_state(s, LAST_STATUS, "auth_required")
        return {"status": "auth_required", "new": 0, "scored": 0, "cursor": -1}

    async with _session() as s:
        cursor = int(await get_state(s, COLLECT_CURSOR) or "0")

    total = len(SEARCH_QUERIES)
    queries = SEARCH_QUERIES[cursor: cursor + COLLECT_QUERY_BATCH]
    next_cursor = cursor + COLLECT_QUERY_BATCH
    if next_cursor >= total:
        next_cursor = 0

    worlds = await asyncio.to_thread(_search, cookie, queries)
    new_count = 0
    for data in worlds:
        async with _session() as s:
            _, created = await upsert_world(s, data)
            if created:
                new_count += 1

    async with _session() as s:
        unscored = await get_unscored_worlds(s)
    scored = 0
    if unscored:
        results = await asyncio.to_thread(_score, unscored)
        async with _session() as s:
            scored = await save_ai_scores(s, results)

    async with _session() as s:
        await set_state(s, COLLECT_CURSOR, str(next_cursor))
        await set_state(s, LAST_COLLECT_AT, datetime.utcnow().isoformat())
        await set_state(s, LAST_STATUS, f"ok new={new_count} scored={scored}")

    return {"status": "ok", "new": new_count, "scored": scored, "cursor": next_cursor}
