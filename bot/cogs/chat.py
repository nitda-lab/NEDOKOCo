import asyncio

import discord
from discord.ext import commands

from bot.chat_ai import chat_reply


class ChatCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return

        user_text = message.clean_content
        for mention in message.mentions:
            user_text = user_text.replace(f"@{mention.display_name}", "").replace(f"@{mention.name}", "")
        user_text = user_text.strip()

        async with message.channel.typing():
            reply = await asyncio.to_thread(chat_reply, user_text)
        await message.reply(reply)


def setup(bot: discord.Bot) -> None:
    bot.add_cog(ChatCog(bot))
