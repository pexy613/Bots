import discord
from discord.ext import commands

import database
from utils import format_money, is_management
from ui import create_embed


async def show_totals(interaction: discord.Interaction, title: str, extra_where: str = ""):
    conn = database.get_connection()
    cursor = conn.cursor()

    query = """
        SELECT COUNT(*),
               COALESCE(SUM(amount_washed), 0),
               COALESCE(SUM(profit_taken), 0)
        FROM washes
        WHERE guild_id = ?
    """
    params = [interaction.guild_id]
    if extra_where:
        query += f" AND {extra_where}"

    cursor.execute(query, params)
    total_washes, total_washed, total_profit = cursor.fetchone()
    conn.close()

    embed = create_embed(
        title,
        color=discord.Color.blue(),
        description="━━━━━━━━━━━━━━━━━━━━━━\nLive totals and payout overview.\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(name="🧼 Total Washes", value=str(total_washes), inline=False)
    embed.add_field(name="💵 Total Washed", value=f"${format_money(total_washed)}", inline=False)
    embed.add_field(name="💰 Total Profit Earned", value=f"${format_money(total_profit)}", inline=False)
    await interaction.response.send_message(embed=embed)


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def allowed(self, interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return False
        return True

    @discord.app_commands.command(name="today", description="Show today's totals.")
    async def today(self, interaction: discord.Interaction):
        if await self.allowed(interaction):
            await show_totals(interaction, "📊 Today's Totals", "DATE(timestamp) = DATE('now')")

    @discord.app_commands.command(name="week", description="Show totals from the last 7 days.")
    async def week(self, interaction: discord.Interaction):
        if await self.allowed(interaction):
            await show_totals(interaction, "📅 Last 7 Days", "timestamp >= DATETIME('now', '-7 days')")

    @discord.app_commands.command(name="month", description="Show totals from the last 30 days.")
    async def month(self, interaction: discord.Interaction):
        if await self.allowed(interaction):
            await show_totals(interaction, "📆 Last 30 Days", "timestamp >= DATETIME('now', '-30 days')")

    @discord.app_commands.command(name="lifetime", description="Show lifetime totals.")
    async def lifetime(self, interaction: discord.Interaction):
        if await self.allowed(interaction):
            await show_totals(interaction, "📈 Lifetime Totals", "")


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
