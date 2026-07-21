import discord
from discord import app_commands
from discord.ext import commands

from .leaderboard import since_for
from ..utils.layouts import error_view, profile_view


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Show a dealer's sales profile")
    @app_commands.describe(member="Whose profile to show (defaults to you)")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        guild_id = str(interaction.guild_id)
        db = self.bot.db

        lifetime = await db.stats(guild_id, seller_id=str(target.id))
        if lifetime["count"] == 0:
            await interaction.response.send_message(
                view=error_view(f"**{target.display_name}** hasn't logged any sales yet."),
                ephemeral=True,
            )
            return

        today = await db.stats(guild_id, since=since_for("today"), seller_id=str(target.id))
        last30 = await db.stats(guild_id, since=since_for("30d"), seller_id=str(target.id))

        full_ranking = await db.leaderboard(guild_id, metric="washed", limit=1000)
        rank = next(
            (i for i, row in enumerate(full_ranking, start=1) if row["seller_id"] == str(target.id)),
            None,
        )

        view = profile_view(target, rank, today, last30, lifetime)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
