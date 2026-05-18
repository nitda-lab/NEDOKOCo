import asyncio

import discord

from collector.pipeline import run_collection
from collector.vrc_client import login

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    asyncio.create_task(_initial_collection())


async def _initial_collection() -> None:
    try:
        result = await asyncio.to_thread(login)
        if result == "email_otp":
            print("VRChat: メールにOTPが送信されました。Discord の /admin vrc_login <code> で入力してください")
            return
        new, qualified = await run_collection()
        print(f"初回収集完了: 新規{new}件 / ぶい睡適合: {qualified}件")
    except Exception as e:
        print(f"初回収集エラー: {e}")


def create_bot() -> discord.Bot:
    bot.load_extension("bot.cogs.suggest")
    bot.load_extension("bot.cogs.admin")
    bot.load_extension("bot.cogs.chat")
    return bot
