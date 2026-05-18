import asyncio
import os
import re

import tweepy

from db.engine import AsyncSessionLocal
from db.repository import add_world, is_tweet_collected, mark_tweet_collected

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

QUERIES = [
    '"ぶい睡" "vrchat.com/home/world" -is:retweet lang:ja',
    '"VR睡眠" "vrchat.com/home/world" -is:retweet lang:ja',
    '"ぶいすい" "vrchat.com/home/world" -is:retweet lang:ja',
    '"buisui" "vrchat.com/home/world" -is:retweet',
]

WORLD_ID_PATTERN = re.compile(
    r"wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

MAX_RESULTS_PER_QUERY = 100


def _extract_world_id(tweet) -> str | None:
    if hasattr(tweet, "entities") and tweet.entities and "urls" in tweet.entities:
        for url_obj in tweet.entities["urls"]:
            m = WORLD_ID_PATTERN.search(url_obj.get("expanded_url", ""))
            if m:
                return m.group(0).lower()
    m = WORLD_ID_PATTERN.search(tweet.text)
    return m.group(0).lower() if m else None


def _tweet_url(tweet_id: str, author_id: str) -> str:
    return f"https://x.com/i/web/status/{tweet_id}"


def _search_tweets(query: str) -> list:
    if not X_BEARER_TOKEN:
        raise RuntimeError("X_BEARER_TOKEN が設定されていません")

    client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
    results = []
    try:
        for tweet in tweepy.Paginator(
            client.search_recent_tweets,
            query=query,
            tweet_fields=["created_at", "entities", "author_id"],
            max_results=100,
        ).flatten(limit=MAX_RESULTS_PER_QUERY):
            results.append(tweet)
    except tweepy.TweepyException:
        pass
    return results


async def collect(session_factory=None) -> int:
    if not X_BEARER_TOKEN:
        raise RuntimeError("X_BEARER_TOKEN が設定されていません")

    from collector.vrc_client import get_world

    new_count = 0
    seen_world_ids: set[str] = set()

    for query in QUERIES:
        tweets = await asyncio.to_thread(_search_tweets, query)

        for tweet in tweets:
            tweet_id = str(tweet.id)

            async with AsyncSessionLocal() as session:
                if await is_tweet_collected(session, tweet_id):
                    continue

            world_id = _extract_world_id(tweet)
            async with AsyncSessionLocal() as session:
                await mark_tweet_collected(session, tweet_id, world_id)

            if not world_id or world_id in seen_world_ids:
                continue
            seen_world_ids.add(world_id)

            world_data = await asyncio.to_thread(get_world, world_id)
            if not world_data:
                continue

            world_data["source_tweet_id"] = tweet_id
            world_data["source_tweet_url"] = _tweet_url(tweet_id, str(tweet.author_id))

            async with AsyncSessionLocal() as session:
                _, created = await add_world(session, world_data)
                if created:
                    new_count += 1

    return new_count
