import asyncio
import os
from datetime import datetime

from collector.ai_scorer import score_worlds
from collector.vrc_client import SEARCH_QUERIES, _search_worlds_with_cookie, get_active_cookie
from db.engine import AsyncSessionLocal
from db.repository import count_qualified, get_unscored_worlds, save_ai_scores, upsert_world
from db.state import COLLECT_CURSOR, LAST_COLLECT_AT, LAST_STATUS, get_state, set_state

COLLECT_QUERY_BATCH = int(os.getenv("COLLECT_QUERY_BATCH", "4"))
SCORE_PER_RUN = int(os.getenv("COLLECT_SCORE_LIMIT", "10"))


def _session():
    return AsyncSessionLocal()


def _search(cookie: str, queries: list[dict]) -> list[dict]:
    return _search_worlds_with_cookie(cookie, queries)


def _score(unscored: list[dict]) -> list[dict]:
    return score_worlds(unscored)


async def run_collection_chunk() -> dict:
    """1回の起動で「採点」か「検索」のどちらか片方だけ行う（60秒制限に収めるため）。
    未採点ワールドがあれば採点を優先し、無ければ次のクエリ束を検索する。"""
    cookie = await get_active_cookie()
    if not cookie:
        async with _session() as s:
            await set_state(s, LAST_STATUS, "auth_required")
        return {"status": "auth_required", "phase": "none", "new": 0, "scored": 0, "cursor": -1}

    async with _session() as s:
        unscored = await get_unscored_worlds(s)
        cursor = int(await get_state(s, COLLECT_CURSOR) or "0")
    unscored = unscored[:SCORE_PER_RUN]

    if unscored:
        results = await asyncio.to_thread(_score, unscored)
        async with _session() as s:
            scored = await save_ai_scores(s, results)
            await set_state(s, LAST_COLLECT_AT, datetime.utcnow().isoformat())
            await set_state(s, LAST_STATUS, f"ok phase=score scored={scored}")
        return {"status": "ok", "phase": "score", "new": 0, "scored": scored, "cursor": cursor}

    total = len(SEARCH_QUERIES)
    queries = SEARCH_QUERIES[cursor: cursor + COLLECT_QUERY_BATCH]
    next_cursor = cursor + COLLECT_QUERY_BATCH
    if next_cursor >= total:
        next_cursor = 0

    worlds = await asyncio.to_thread(_search, cookie, queries)
    new_count = 0
    async with _session() as s:
        for data in worlds:
            _, created = await upsert_world(s, data)
            if created:
                new_count += 1
        await set_state(s, COLLECT_CURSOR, str(next_cursor))
        await set_state(s, LAST_COLLECT_AT, datetime.utcnow().isoformat())
        await set_state(s, LAST_STATUS, f"ok phase=search new={new_count}")

    return {"status": "ok", "phase": "search", "new": new_count, "scored": 0, "cursor": next_cursor}


async def run_collection() -> tuple[int, int]:
    """全クエリを一括収集しAI評価まで行う。(新規件数, ぶい睡適合件数) を返す。

    Discord bot の一括収集（初回起動 / `/admin refresh` / `/admin vrc_login`）用。
    cron は `run_collection_chunk()` でクエリを分割実行する。
    """
    cookie = await get_active_cookie()
    if not cookie:
        async with _session() as s:
            await set_state(s, LAST_STATUS, "auth_required")
        raise RuntimeError("VRChat認証が必要です。/admin vrc_login でOTPを入力してください")

    worlds = await asyncio.to_thread(_search, cookie, SEARCH_QUERIES)
    new_count = 0
    for data in worlds:
        async with _session() as s:
            _, created = await upsert_world(s, data)
            if created:
                new_count += 1

    async with _session() as s:
        unscored = await get_unscored_worlds(s)
    if unscored:
        results = await asyncio.to_thread(_score, unscored)
        async with _session() as s:
            await save_ai_scores(s, results)

    async with _session() as s:
        qualified = await count_qualified(s)
        await set_state(s, LAST_COLLECT_AT, datetime.utcnow().isoformat())
        await set_state(s, LAST_STATUS, f"ok new={new_count} qualified={qualified}")

    return new_count, qualified
