import asyncio
import re
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.embeds import build_world_embed
from collector.pipeline import run_collection
from collector.vrc_client import get_active_cookie, get_world, verify_email_otp
from db.engine import AsyncSessionLocal
from db.models import World
from db.repository import upsert_world
from sqlalchemy import select

WORLD_ID_PATTERN = re.compile(
    r"wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

_last_refresh: datetime | None = None
REFRESH_COOLDOWN_HOURS = 6


def parse_world_id(value: str) -> str | None:
    m = WORLD_ID_PATTERN.search(value)
    return m.group(0).lower() if m else None


class AdminCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    admin = discord.SlashCommandGroup(
        "admin",
        "管理者コマンド",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    @admin.command(name="vrc_login", description="VRChatメールOTPを入力してログイン完了")
    async def vrc_login(
        self,
        ctx: discord.ApplicationContext,
        code: discord.Option(str, "メールに届いた6桁のOTPコード"),
    ) -> None:
        try:
            await verify_email_otp(code)
        except Exception as e:
            await ctx.respond(f"❌ OTP検証失敗: {e}", ephemeral=True)
            return

        await ctx.respond("✅ VRChatログイン完了。ワールド収集を開始します...", ephemeral=True)

        async def _collect() -> None:
            try:
                new, qualified = await run_collection()
                await ctx.followup.send(f"収集完了: 新規{new}件 / ぶい睡適合: {qualified}件", ephemeral=True)
            except Exception as e:
                await ctx.followup.send(f"収集エラー: {e}", ephemeral=True)

        asyncio.create_task(_collect())

    @admin.command(name="refresh", description="VRChat APIからワールドを再取得してDBを更新")
    async def refresh(self, ctx: discord.ApplicationContext) -> None:
        global _last_refresh
        if _last_refresh and datetime.utcnow() - _last_refresh < timedelta(hours=REFRESH_COOLDOWN_HOURS):
            remaining = REFRESH_COOLDOWN_HOURS - int((datetime.utcnow() - _last_refresh).seconds / 3600)
            await ctx.respond(f"クールダウン中です（あと約{remaining}時間）", ephemeral=True)
            return

        await ctx.respond("VRChat APIからワールドを取得中...", ephemeral=True)
        _last_refresh = datetime.utcnow()

        async def _run() -> None:
            try:
                new, qualified = await run_collection()
                await ctx.followup.send(f"完了: 新規{new}件 / ぶい睡適合: {qualified}件", ephemeral=True)
            except Exception as e:
                await ctx.followup.send(f"エラーが発生しました: {e}", ephemeral=True)

        asyncio.create_task(_run())

    @admin.command(name="add_world", description="VRChat URLまたはIDでワールドを手動登録")
    async def add_world_cmd(
        self,
        ctx: discord.ApplicationContext,
        vrchat_url_or_id: discord.Option(str, "VRChat URL または wrld_xxx 形式のID"),
    ) -> None:
        wid = parse_world_id(vrchat_url_or_id)
        if not wid:
            await ctx.respond("有効なVRChat URLまたはワールドIDを入力してください", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        cookie = await get_active_cookie()
        if not cookie:
            await ctx.followup.send(
                "VRChat認証が必要です。`/admin vrc_login` でOTPを入力してください", ephemeral=True
            )
            return

        world_data = await asyncio.to_thread(get_world, wid, cookie)
        if not world_data:
            await ctx.followup.send(f"ワールド情報を取得できませんでした: `{wid}`", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            world, created = await upsert_world(session, world_data)

        msg = f"登録しました: **{world.name}**" if created else f"更新しました: **{world.name}**"
        await ctx.followup.send(msg, ephemeral=True)

    @admin.command(name="preview", description="ワールドのEmbed表示を確認")
    async def preview(
        self,
        ctx: discord.ApplicationContext,
        world_id: discord.Option(str, "ワールドID (wrld_xxx...)"),
    ) -> None:
        wid = parse_world_id(world_id)
        if not wid:
            await ctx.respond("有効なワールドIDを入力してください", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(World).where(World.world_id == wid))
            world = result.scalar_one_or_none()

        if not world:
            await ctx.respond(f"`{wid}` が見つかりません", ephemeral=True)
            return

        embed, view = build_world_embed(world)
        await ctx.respond(embed=embed, view=view, ephemeral=True)


def setup(bot: discord.Bot) -> None:
    bot.add_cog(AdminCog(bot))
