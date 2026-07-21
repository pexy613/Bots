import os
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database
from ui import create_embed
from utils import format_money, is_management

_SETTINGS = {
    "dashboard_channel": "combined_dashboard_channel_id",
    "dashboard_message": "combined_dashboard_message_id",
    "leaderboard_channel": "combined_leaderboard_channel_id",
    "leaderboard_message": "combined_leaderboard_message_id",
}

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GUNSALES_DB_PATH = os.path.join(_BASE_DIR, "GunSalesBot", "data", "gunsales.db")


def _parse_target_guild_id() -> Optional[int]:
    raw = (os.getenv("COMBINED_PANELS_GUILD_ID") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


_TARGET_GUILD_ID = _parse_target_guild_id()
_TARGET_GUILD = discord.Object(id=_TARGET_GUILD_ID or 1)


def _enabled_for_guild(guild_id: int) -> bool:
    return _TARGET_GUILD_ID is not None and guild_id == _TARGET_GUILD_ID


def _fetchone_washes(guild_id: int, extra_where: str = ""):
    query = """
        SELECT
            COUNT(*),
            COALESCE(SUM(amount_washed), 0),
            COALESCE(SUM(profit_taken), 0)
        FROM washes
        WHERE guild_id = ?
    """
    params = [guild_id]
    if extra_where:
        query += f" AND {extra_where}"
    return database.fetchone(query, params)


def _fetchone_gunsales(guild_id: int, extra_where: str = ""):
    if not os.path.exists(_GUNSALES_DB_PATH):
        return (0, 0, 0)

    conn = sqlite3.connect(_GUNSALES_DB_PATH)
    cur = conn.cursor()
    query = """
        SELECT
            COUNT(*),
            COALESCE(SUM(total_amount), 0),
            COALESCE(SUM(profit), 0)
        FROM sales
        WHERE guild_id = ?
    """
    params = [str(guild_id)]
    if extra_where:
        query += f" AND {extra_where}"

    cur.execute(query, params)
    row = cur.fetchone() or (0, 0, 0)
    conn.close()
    return row


def _top_washes(guild_id: int, limit: int = 10):
    return database.fetchall(
        """
        SELECT
            user,
            user_id,
            COUNT(*) AS washes,
            COALESCE(SUM(amount_washed), 0) AS washed,
            COALESCE(SUM(profit_taken), 0) AS profit
        FROM washes
        WHERE guild_id = ?
        GROUP BY user_id
        ORDER BY washed DESC
        LIMIT ?
        """,
        (guild_id, limit),
    )


def _top_gunsales(guild_id: int, limit: int = 10):
    if not os.path.exists(_GUNSALES_DB_PATH):
        return []

    conn = sqlite3.connect(_GUNSALES_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            seller_name,
            seller_id,
            COUNT(*) AS sales,
            COALESCE(SUM(total_amount), 0) AS washed,
            COALESCE(SUM(profit), 0) AS profit
        FROM sales
        WHERE guild_id = ?
        GROUP BY seller_id
        ORDER BY washed DESC
        LIMIT ?
        """,
        (str(guild_id), limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _stats_block(washed: int, profit: int, count: int, label: str) -> str:
    return (
        f"Washed: ${format_money(washed)}\n"
        f"Profit: ${format_money(profit)}\n"
        f"{label}: {count}"
    )


def _rank_line(position: int, name: str, washed: int, profit: int, count: int, label: str) -> str:
    medals = ["🥇", "🥈", "🥉"]
    prefix = medals[position - 1] if position <= 3 else f"#{position}"
    return (
        f"{prefix} {name}\n"
        f"${format_money(washed)} washed • ${format_money(profit)} profit • {count} {label.lower()}"
    )


def build_combined_dashboard_embed(guild: Optional[discord.Guild], guild_id: int) -> discord.Embed:
    wash_today = _fetchone_washes(guild_id, "DATE(timestamp) = DATE('now')")
    wash_week = _fetchone_washes(guild_id, "timestamp >= DATETIME('now', '-7 days')")
    wash_month = _fetchone_washes(guild_id, "timestamp >= DATETIME('now', '-30 days')")
    wash_life = _fetchone_washes(guild_id)

    # GunSalesBot stores ISO timestamps; trim to yyyy-mm-dd hh:mm:ss for SQLite datetime ops.
    gun_today = _fetchone_gunsales(guild_id, "DATE(SUBSTR(created_at, 1, 19)) = DATE('now')")
    gun_week = _fetchone_gunsales(guild_id, "DATETIME(SUBSTR(created_at, 1, 19)) >= DATETIME('now', '-7 days')")
    gun_month = _fetchone_gunsales(guild_id, "DATETIME(SUBSTR(created_at, 1, 19)) >= DATETIME('now', '-30 days')")
    gun_life = _fetchone_gunsales(guild_id)

    guild_name = guild.name if guild else f"Guild {guild_id}"
    embed = create_embed(
        "🏦 Combined Ops Dashboard",
        color=discord.Color.blurple(),
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Server-specific combined stats for {guild_name}\n"
            "Gun Logs and Money Washes in one panel\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
    )

    embed.add_field(name="🔫 Gun Logs • Today", value=_stats_block(gun_today[1], gun_today[2], gun_today[0], "Sales"), inline=True)
    embed.add_field(name="🧼 Money Washes • Today", value=_stats_block(wash_today[1], wash_today[2], wash_today[0], "Washes"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(name="🔫 Gun Logs • Last 7 Days", value=_stats_block(gun_week[1], gun_week[2], gun_week[0], "Sales"), inline=True)
    embed.add_field(name="🧼 Money Washes • Last 7 Days", value=_stats_block(wash_week[1], wash_week[2], wash_week[0], "Washes"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(name="🔫 Gun Logs • Last 30 Days", value=_stats_block(gun_month[1], gun_month[2], gun_month[0], "Sales"), inline=True)
    embed.add_field(name="🧼 Money Washes • Last 30 Days", value=_stats_block(wash_month[1], wash_month[2], wash_month[0], "Washes"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(name="🔫 Gun Logs • Lifetime", value=_stats_block(gun_life[1], gun_life[2], gun_life[0], "Sales"), inline=True)
    embed.add_field(name="🧼 Money Washes • Lifetime", value=_stats_block(wash_life[1], wash_life[2], wash_life[0], "Washes"), inline=True)
    embed.set_footer(text="The Ledger • Combined dashboard")
    return embed


def build_combined_leaderboard_embed(guild: Optional[discord.Guild], guild_id: int) -> discord.Embed:
    wash_rows = _top_washes(guild_id, limit=10)
    gun_rows = _top_gunsales(guild_id, limit=10)

    guild_name = guild.name if guild else f"Guild {guild_id}"
    embed = create_embed(
        "🏆 Combined Leaderboard",
        color=discord.Color.gold(),
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Server-specific rankings for {guild_name}\n"
            "Left side = Gun Logs • Right side = Money Washes\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
    )

    if gun_rows:
        gun_lines = []
        for i, row in enumerate(gun_rows, start=1):
            seller_name, _seller_id, sales, washed, profit = row
            gun_lines.append(_rank_line(i, seller_name, washed, profit, sales, "Sales"))
        gun_value = "\n\n".join(gun_lines)
    else:
        gun_value = "No gun sales logged yet."

    if wash_rows:
        wash_lines = []
        for i, row in enumerate(wash_rows, start=1):
            saved_name, user_id, washes, washed, profit = row
            member = guild.get_member(int(user_id)) if guild else None
            name = member.display_name if member else saved_name
            wash_lines.append(_rank_line(i, name, washed, profit, washes, "Washes"))
        wash_value = "\n\n".join(wash_lines)
    else:
        wash_value = "No washes logged yet."

    embed.add_field(name="🔫 Gun Logs", value=gun_value[:1024], inline=True)
    embed.add_field(name="🧼 Money Washes", value=wash_value[:1024], inline=True)
    embed.set_footer(text="The Ledger • Combined leaderboard")
    return embed


async def update_live_combined_dashboard(bot: commands.Bot, guild_id: int):
    if not _enabled_for_guild(guild_id):
        return

    channel_id = database.get_setting(guild_id, _SETTINGS["dashboard_channel"])
    message_id = database.get_setting(guild_id, _SETTINGS["dashboard_message"])
    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return

    guild = bot.get_guild(guild_id)
    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_combined_dashboard_embed(guild, guild_id))
    except Exception as e:
        print(f"Combined dashboard update failed for guild {guild_id}: {e}")


async def update_live_combined_leaderboard(bot: commands.Bot, guild_id: int):
    if not _enabled_for_guild(guild_id):
        return

    channel_id = database.get_setting(guild_id, _SETTINGS["leaderboard_channel"])
    message_id = database.get_setting(guild_id, _SETTINGS["leaderboard_message"])
    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return

    guild = bot.get_guild(guild_id)
    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_combined_leaderboard_embed(guild, guild_id))
    except Exception as e:
        print(f"Combined leaderboard update failed for guild {guild_id}: {e}")


class CombinedPanelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.refresh_panels.start()

    def cog_unload(self):
        self.refresh_panels.cancel()

    async def _can_use(self, interaction: discord.Interaction) -> bool:
        if not _enabled_for_guild(interaction.guild_id):
            await interaction.response.send_message(
                "❌ Combined panels are enabled only for the configured server.",
                ephemeral=True,
            )
            return False

        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return False
        return True

    @tasks.loop(seconds=60)
    async def refresh_panels(self):
        if not _TARGET_GUILD_ID:
            return
        await update_live_combined_dashboard(self.bot, _TARGET_GUILD_ID)
        await update_live_combined_leaderboard(self.bot, _TARGET_GUILD_ID)

    @refresh_panels.before_loop
    async def before_refresh_panels(self):
        await self.bot.wait_until_ready()

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="combineddashboard", description="Show combined gun+washes dashboard (this server only).")
    async def combineddashboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return
        await interaction.response.send_message(
            embed=build_combined_dashboard_embed(interaction.guild, interaction.guild_id)
        )

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="setupcombineddashboard", description="Create a live combined dashboard panel (this server only).")
    async def setupcombineddashboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        message = await interaction.channel.send(embed=build_combined_dashboard_embed(interaction.guild, interaction.guild_id))
        database.save_setting(interaction.guild_id, _SETTINGS["dashboard_channel"], str(interaction.channel_id))
        database.save_setting(interaction.guild_id, _SETTINGS["dashboard_message"], str(message.id))
        await interaction.followup.send("✅ Live combined dashboard created for this server.", ephemeral=True)

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="resetcombineddashboard", description="Reset the live combined dashboard panel (this server only).")
    async def resetcombineddashboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        channel_id = database.get_setting(interaction.guild_id, _SETTINGS["dashboard_channel"])
        message_id = database.get_setting(interaction.guild_id, _SETTINGS["dashboard_message"])
        if channel_id and message_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
            except Exception:
                pass

        database.save_setting(interaction.guild_id, _SETTINGS["dashboard_channel"], "")
        database.save_setting(interaction.guild_id, _SETTINGS["dashboard_message"], "")
        await interaction.followup.send("✅ Combined dashboard reset for this server.", ephemeral=True)

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="combinedleaderboard", description="Show combined gun+washes leaderboard (this server only).")
    async def combinedleaderboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return
        await interaction.response.send_message(
            embed=build_combined_leaderboard_embed(interaction.guild, interaction.guild_id)
        )

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="setupcombinedleaderboard", description="Create a live combined leaderboard panel (this server only).")
    async def setupcombinedleaderboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        message = await interaction.channel.send(embed=build_combined_leaderboard_embed(interaction.guild, interaction.guild_id))
        database.save_setting(interaction.guild_id, _SETTINGS["leaderboard_channel"], str(interaction.channel_id))
        database.save_setting(interaction.guild_id, _SETTINGS["leaderboard_message"], str(message.id))
        await interaction.followup.send("✅ Live combined leaderboard created for this server.", ephemeral=True)

    @app_commands.guilds(_TARGET_GUILD)
    @app_commands.command(name="resetcombinedleaderboard", description="Reset the live combined leaderboard panel (this server only).")
    async def resetcombinedleaderboard(self, interaction: discord.Interaction):
        if not await self._can_use(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        channel_id = database.get_setting(interaction.guild_id, _SETTINGS["leaderboard_channel"])
        message_id = database.get_setting(interaction.guild_id, _SETTINGS["leaderboard_message"])
        if channel_id and message_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
            except Exception:
                pass

        database.save_setting(interaction.guild_id, _SETTINGS["leaderboard_channel"], "")
        database.save_setting(interaction.guild_id, _SETTINGS["leaderboard_message"], "")
        await interaction.followup.send("✅ Combined leaderboard reset for this server.", ephemeral=True)


async def setup(bot: commands.Bot):
    if _TARGET_GUILD_ID is None:
        raise RuntimeError("COMBINED_PANELS_GUILD_ID is not set or invalid.")
    await bot.add_cog(CombinedPanelsCog(bot))
