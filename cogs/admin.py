import csv
import os
import shutil
from datetime import datetime

import discord
from discord.ext import commands

import database
from utils import is_management
from cogs.live_dashboard import update_live_dashboard
from cogs.leaderboard import update_live_leaderboard
from cogs.goals import update_goal_dashboard


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="resetwashes", description="Delete all wash logs and reset totals.")
    async def resetwashes(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        database.execute("DELETE FROM washes WHERE guild_id = ?", (interaction.guild_id,))

        await update_live_dashboard(self.bot, interaction.guild_id)
        await update_live_leaderboard(self.bot, interaction.guild_id)
        await update_goal_dashboard(self.bot, interaction.guild_id)

        await interaction.followup.send(
            "✅ All wash data has been reset. Dashboard totals are now 0.",
            ephemeral=True
        )

    @discord.app_commands.command(name="deletewash", description="Delete a single wash log by ID.")
    async def deletewash(self, interaction: discord.Interaction, wash_id: int):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        row = database.fetchone(
            "SELECT id FROM washes WHERE id = ? AND guild_id = ?",
            (wash_id, interaction.guild_id)
        )
        if not row:
            await interaction.followup.send(f"❌ No wash found with ID #{wash_id}.", ephemeral=True)
            return

        database.execute(
            "DELETE FROM washes WHERE id = ? AND guild_id = ?",
            (wash_id, interaction.guild_id)
        )

        await update_live_dashboard(self.bot, interaction.guild_id)
        await update_live_leaderboard(self.bot, interaction.guild_id)
        await update_goal_dashboard(self.bot, interaction.guild_id)

        await interaction.followup.send(
            f"✅ Wash #{wash_id} deleted. Dashboard, leaderboard, and goal progress updated.",
            ephemeral=True
        )

    @discord.app_commands.command(name="export", description="Export all wash data to CSV.")
    async def export(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        filename = f"wash_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user, user_id, amount_washed, percentage_taken, profit_taken, timestamp
            FROM washes
            WHERE guild_id = ?
            ORDER BY id ASC
        """, (interaction.guild_id,))
        rows = cursor.fetchall()
        conn.close()

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "user", "user_id", "amount_washed", "percentage_taken", "profit_taken", "timestamp"])
            writer.writerows(rows)

        await interaction.followup.send("✅ Export ready.", file=discord.File(filename), ephemeral=True)
        os.remove(filename)

    @discord.app_commands.command(name="backup", description="Create a backup of the database. Bot owner only.")
    async def backup(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return

        os.makedirs("backups", exist_ok=True)
        backup_name = f"backups/laundering_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copyfile("laundering.db", backup_name)
        await interaction.response.send_message("✅ Backup created.", file=discord.File(backup_name), ephemeral=True)

    @discord.app_commands.command(name="refreshdashboard", description="Force refresh the live dashboard and leaderboard.")
    async def refreshdashboard(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message("❌ Only Management can use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await update_live_dashboard(self.bot, interaction.guild_id)
        await update_live_leaderboard(self.bot, interaction.guild_id)
        await interaction.followup.send("✅ Live dashboard and leaderboard refreshed.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
