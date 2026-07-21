import discord
from discord import app_commands
from discord.ext import commands

from utils.layouts import error_view, settings_view


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    config_group = app_commands.Group(
        name="config", description="[Admin] Configure the sales bot for this server"
    )

    @config_group.command(name="commission", description="[Admin] Set the seller commission percent")
    @app_commands.describe(percent="Commission percent applied to new sales, e.g. 20 for 20%")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def commission(self, interaction: discord.Interaction, percent: app_commands.Range[float, 0, 100]):
        await self.bot.db.set_commission(str(interaction.guild_id), percent)
        await interaction.response.send_message(f"💰 Commission set to **{percent}%** for future sales.")

    @config_group.command(name="logchannel", description="[Admin] Set a channel where every sale receipt is also posted")
    @app_commands.describe(channel="Channel to post sale receipts to")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def logchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.set_log_channel(str(interaction.guild_id), str(channel.id))
        await interaction.response.send_message(f"📌 Sale receipts will also be posted in {channel.mention}.")

    @config_group.command(name="show", description="Show the current bot configuration")
    async def show(self, interaction: discord.Interaction):
        settings = await self.bot.db.get_settings(str(interaction.guild_id))
        channel_text = "Not set"
        if settings["log_channel_id"]:
            channel = interaction.guild.get_channel(int(settings["log_channel_id"]))
            channel_text = channel.mention if channel else "Unknown channel"
        view = settings_view(settings["commission_percent"], channel_text)
        await interaction.response.send_message(view=view)

    @commission.error
    @logchannel.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                view=error_view("You need the **Manage Server** permission to do that."),
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
