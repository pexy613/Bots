import discord
from discord.ext import commands

from utils import is_management
from cogs.live_dashboard import build_dashboard_embed


class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="dashboard", description="Show the panel dashboard.")
    async def dashboard(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        await interaction.response.send_message(embed=build_dashboard_embed(interaction.guild_id))


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
