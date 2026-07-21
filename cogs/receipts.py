import discord
from discord.ext import commands

import database
from utils import format_money, is_management
from ui import create_embed


class ReceiptsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="receipt", description="View a wash receipt by ID.")
    async def receipt(self, interaction: discord.Interaction, wash_id: int):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user, amount_washed, percentage_taken, profit_taken, timestamp
            FROM washes
            WHERE id = ? AND guild_id = ?
        """, (wash_id, interaction.guild_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            await interaction.response.send_message("❌ No wash found with that ID.", ephemeral=True)
            return

        wid, user, washed, percentage, profit, timestamp = row
        embed = create_embed(
            f"🧾 Wash Receipt #{wid}",
            color=discord.Color.teal(),
            description="━━━━━━━━━━━━━━━━━━━━━━\nStructured wash details and payout summary.\n━━━━━━━━━━━━━━━━━━━━━━"
        )
        embed.add_field(name="👤 Logged By", value=user, inline=False)
        embed.add_field(name="💵 Amount Washed", value=f"${format_money(washed)}", inline=False)
        embed.add_field(name="📉 Percentage Taken", value=f"{percentage}%", inline=False)
        embed.add_field(name="💰 Profit Earned", value=f"${format_money(profit)}", inline=False)
        embed.add_field(name="🕒 Time", value=str(timestamp), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReceiptsCog(bot))
