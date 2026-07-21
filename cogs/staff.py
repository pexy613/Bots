import discord
from discord.ext import commands

import database
from utils import format_money, is_management
from ui import create_embed


class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="staff", description="Show stats for a staff member.")
    async def staff(self, interaction: discord.Interaction, member: discord.Member):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount_washed), 0), COALESCE(SUM(profit_taken), 0),
                   COALESCE(AVG(amount_washed), 0), COALESCE(MAX(amount_washed), 0)
            FROM washes
            WHERE user_id = ? AND guild_id = ?
        """, (member.id, interaction.guild_id))
        washes, washed, profit, avg_wash, biggest = cursor.fetchone()
        conn.close()

        embed = create_embed(
            f"👤 Staff Stats: {member.display_name}",
            color=discord.Color.blurple(),
            description="━━━━━━━━━━━━━━━━━━━━━━\nPerformance summary for this staff member.\n━━━━━━━━━━━━━━━━━━━━━━"
        )
        embed.add_field(name="🧼 Total Washes", value=str(washes), inline=False)
        embed.add_field(name="💵 Total Washed", value=f"${format_money(washed)}", inline=False)
        embed.add_field(name="💰 Total Profit", value=f"${format_money(profit)}", inline=False)
        embed.add_field(name="📊 Average Wash", value=f"${format_money(avg_wash)}", inline=False)
        embed.add_field(name="🔥 Biggest Wash", value=f"${format_money(biggest)}", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(StaffCog(bot))
