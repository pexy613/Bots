import discord
from discord import app_commands
from discord.ext import commands

from cogs.leaderboard import since_for
from utils.layouts import dashboard_view, error_view


async def _build_dashboard_view(bot: commands.Bot, guild: discord.Guild) -> discord.ui.LayoutView:
    guild_id = str(guild.id)
    db = bot.db

    today = await db.stats(guild_id, since=since_for("today"))
    last7 = await db.stats(guild_id, since=since_for("7d"))
    last30 = await db.stats(guild_id, since=since_for("30d"))
    lifetime = await db.stats(guild_id)

    top_rows = await db.leaderboard(guild_id, metric="washed", limit=1)
    top_seller = dict(top_rows[0]) if top_rows else None

    return dashboard_view(guild.name, today, last7, last30, lifetime, top_seller)


async def update_live_dashboard(bot: commands.Bot, guild: discord.Guild) -> None:
    """Refreshes the standing dashboard panel (if one was set up) after a sale changes."""
    settings = await bot.db.get_settings(str(guild.id))
    channel_id = settings["dashboard_channel_id"]
    message_id = settings["dashboard_message_id"]
    if not channel_id or not message_id:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(message_id))
    except (discord.NotFound, discord.Forbidden):
        await bot.db.set_dashboard_panel(str(guild.id), None, None)
        return

    view = await _build_dashboard_view(bot, guild)
    try:
        await message.edit(view=view)
    except discord.HTTPException:
        pass


class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    dashboard_group = app_commands.Group(name="dashboard", description="Show or set up the live sales dashboard")

    @dashboard_group.command(name="show", description="Show the sales dashboard (one-time snapshot)")
    async def show(self, interaction: discord.Interaction):
        view = await _build_dashboard_view(self.bot, interaction.guild)
        await interaction.response.send_message(view=view)

    @dashboard_group.command(
        name="panel", description="[Admin] Post a live dashboard that updates after every sale"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        view = await _build_dashboard_view(self.bot, interaction.guild)
        await interaction.response.send_message(view=view)
        message = await interaction.original_response()
        await self.bot.db.set_dashboard_panel(
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
    await bot.add_cog(Dashboard(bot))
