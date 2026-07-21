from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.layouts import error_view, leaderboard_view

TIMEFRAME_CHOICES = [
    app_commands.Choice(name="Today", value="today"),
    app_commands.Choice(name="Last 7 Days", value="7d"),
    app_commands.Choice(name="Last 30 Days", value="30d"),
    app_commands.Choice(name="Lifetime", value="lifetime"),
]

METRIC_CHOICES = [
    app_commands.Choice(name="Amount Washed", value="washed"),
    app_commands.Choice(name="Profit", value="profit"),
    app_commands.Choice(name="Number of Sales", value="count"),
]

TIMEFRAME_LABELS = {
    "today": "Today",
    "7d": "Last 7 Days",
    "30d": "Last 30 Days",
    "lifetime": "Lifetime",
}

METRIC_LABELS = {
    "washed": "Amount Washed",
    "profit": "Profit",
    "count": "Number of Sales",
}

# The live leaderboard panel is always lifetime / amount washed — the metric that
# matters for a standing "who's on top" board that updates after every sale.
LIVE_TIMEFRAME = "lifetime"
LIVE_METRIC = "washed"


def since_for(timeframe: str) -> Optional[str]:
    now = datetime.now(timezone.utc)
    if timeframe == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "7d":
        start = now - timedelta(days=7)
    elif timeframe == "30d":
        start = now - timedelta(days=30)
    else:
        return None
    return start.isoformat()


async def update_live_leaderboard(bot: commands.Bot, guild: discord.Guild) -> None:
    """Refreshes the standing leaderboard panel (if one was set up) after a sale changes."""
    settings = await bot.db.get_settings(str(guild.id))
    channel_id = settings["leaderboard_channel_id"]
    message_id = settings["leaderboard_message_id"]
    if not channel_id or not message_id:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(message_id))
    except (discord.NotFound, discord.Forbidden):
        await bot.db.set_leaderboard_panel(str(guild.id), None, None)
        return

    rows = await bot.db.leaderboard(str(guild.id), metric=LIVE_METRIC, limit=10)
    view = leaderboard_view(TIMEFRAME_LABELS[LIVE_TIMEFRAME], METRIC_LABELS[LIVE_METRIC], rows)
    try:
        await message.edit(view=view)
    except discord.HTTPException:
        pass


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    leaderboard_group = app_commands.Group(name="leaderboard", description="Show or set up the weapon dealer leaderboard")

    @leaderboard_group.command(name="show", description="Show the top weapon dealers (one-time snapshot)")
    @app_commands.choices(timeframe=TIMEFRAME_CHOICES, metric=METRIC_CHOICES)
    async def show(
        self,
        interaction: discord.Interaction,
        timeframe: app_commands.Choice[str] = None,
        metric: app_commands.Choice[str] = None,
    ):
        timeframe_value = timeframe.value if timeframe else "lifetime"
        metric_value = metric.value if metric else "washed"

        rows = await self.bot.db.leaderboard(
            str(interaction.guild_id),
            since=since_for(timeframe_value),
            metric=metric_value,
            limit=10,
        )
        view = leaderboard_view(TIMEFRAME_LABELS[timeframe_value], METRIC_LABELS[metric_value], rows)
        await interaction.response.send_message(view=view)

    @leaderboard_group.command(
        name="panel", description="[Admin] Post a live leaderboard that updates after every sale"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        rows = await self.bot.db.leaderboard(str(interaction.guild_id), metric=LIVE_METRIC, limit=10)
        view = leaderboard_view(TIMEFRAME_LABELS[LIVE_TIMEFRAME], METRIC_LABELS[LIVE_METRIC], rows)
        await interaction.response.send_message(view=view)
        message = await interaction.original_response()
        await self.bot.db.set_leaderboard_panel(
            str(interaction.guild_id), str(interaction.channel_id), str(message.id)
        )

    @panel.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                view=error_view("You need the **Manage Server** permission to do that."),
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
