import discord
from discord.ext import commands

from bot.embeds import build_world_embed
from db.engine import AsyncSessionLocal
from db.repository import get_random_worlds, update_worlds_suggested


class SuggestCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(name="suggest", description="今夜のぶい睡ワールドを5件提案します 🌙")
    async def suggest(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer()

        async with AsyncSessionLocal() as session:
            worlds = await get_random_worlds(session, count=5)

        if not worlds:
            await ctx.followup.send("ワールドがまだ登録されていません。しばらくお待ちください...")
            return

        embeds = []
        views = []
        for i, world in enumerate(worlds):
            embed, view = build_world_embed(world, show_header=(i == 0))
            embeds.append(embed)
            views.append(view)

        # 最初のメッセージに全Embedをまとめて送信（Discordは1メッセージ10件まで）
        # Viewは最初のワールドのボタンのみ添付（複数Viewは1メッセージに1つのみ）
        # 各ワールドのリンクはEmbedのdescriptionに含める
        await ctx.followup.send(content="🌙 AIがぶい睡に適したワールドをピックアップしました", embeds=embeds)

        async with AsyncSessionLocal() as session:
            await update_worlds_suggested(session, [w.world_id for w in worlds])


def setup(bot: discord.Bot) -> None:
    bot.add_cog(SuggestCog(bot))
