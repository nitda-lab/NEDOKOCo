import json

import discord

from db.models import World

EMBED_COLOR = 0x7B68EE  # midnight purple


def build_world_embed(world: World, show_header: bool = False) -> tuple[discord.Embed, discord.ui.View]:
    tags = []
    if world.tags:
        try:
            raw = json.loads(world.tags)
            tags = [t for t in raw if not t.startswith("author_tag_")]
        except (json.JSONDecodeError, TypeError):
            tags = []

    tags_display = "　".join(tags[:6]) if tags else "—"
    desc_preview = (world.description or "")[:150]
    if world.description and len(world.description) > 150:
        desc_preview += "..."

    embed = discord.Embed(
        title=world.name,
        url=world.vrc_url,
        color=EMBED_COLOR,
    )
    if show_header:
        embed.set_author(name="🌙 今夜のぶい睡ワールド")
    embed.description = f"by {world.author_name}"
    if world.image_url:
        embed.set_thumbnail(url=world.image_url)
    if world.capacity:
        embed.add_field(name="👥 最大人数", value=f"{world.capacity}人", inline=True)
    embed.add_field(name="🏷️ タグ", value=tags_display, inline=True)
    if desc_preview:
        embed.add_field(name="📝 説明", value=desc_preview, inline=False)
    embed.set_footer(text="ぶい睡 Bot • 快眠 VR 生活を ✨")
    embed.timestamp = discord.utils.utcnow()

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="VRChatで開く", style=discord.ButtonStyle.link, url=world.vrc_url))

    return embed, view
