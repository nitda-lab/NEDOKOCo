import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from bot.client import create_bot
from db.engine import init_db

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


async def main() -> None:
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError(".env に DISCORD_BOT_TOKEN が設定されていません")

    await init_db()
    bot = create_bot()
    await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
