"""GitHub Actions から実行する収集スクリプト。
Neon(app_state) に保存済みの VRChat 認証クッキーを使い、全クエリ収集 + nanoGPT 採点を行う。
Vercel の60秒制限を受けないため、ここで全件を一括処理する。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.pipeline import run_collection  # noqa: E402
from db.engine import init_db  # noqa: E402


async def main() -> None:
    await init_db()
    new, qualified = await run_collection()
    print(f"done: new={new} qualified={qualified}")


if __name__ == "__main__":
    asyncio.run(main())
