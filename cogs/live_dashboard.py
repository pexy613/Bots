import discord
from discord.ext import commands

import database
from utils import is_management
from ui import dashboard_embed


def get_totals(guild_id, extra_where=""):
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


def build_dashboard_embed(guild_id):
    today = get_totals(guild_id, "DATE(timestamp) = DATE('now')")
    week = get_totals(guild_id, "timestamp >= DATETIME('now', '-7 days')")
    month = get_totals(guild_id, "timestamp >= DATETIME('now', '-30 days')")
    lifetime = get_totals(guild_id)

    top_user = database.fetchone("""
        SELECT user, COALESCE(SUM(amount_washed), 0)
        FROM washes
        WHERE guild_id = ?
        GROUP BY user
        ORDER BY SUM(amount_washed) DESC
        LIMIT 1
    """, (guild_id,))

    return dashboard_embed(today, week, month, lifetime, top_user)


async def update_live_dashboard(bot, guild_id):
    channel_id = database.get_setting(guild_id, "dashboard_channel_id")
    message_id = database.get_setting(guild_id, "dashboard_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return

    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_dashboard_embed(guild_id))
    except Exception as e:
        print(f"Live dashboard update failed: {e}")


class LiveDashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message(
                "❌ Only Management can use this command.",
                ephemeral=True
            )
            return False

        return True

    @discord.app_commands.command(name="setupdashboard", description="Create the permanent live dashboard.")
    async def setupdashboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            message = await interaction.channel.send(embed=build_dashboard_embed(interaction.guild_id))
            database.save_setting(interaction.guild_id, "dashboard_channel_id", str(interaction.channel.id))
            database.save_setting(interaction.guild_id, "dashboard_message_id", str(message.id))
        except Exception as e:
            await interaction.followup.send(
                f"❌ Dashboard setup failed: `{e}`",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            "✅ Live dashboard created.",
            ephemeral=True
        )

    @discord.app_commands.command(name="resetdashboard", description="Reset the saved live dashboard message.")
    async def resetdashboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        channel_id = database.get_setting(interaction.guild_id, "dashboard_channel_id")
        message_id = database.get_setting(interaction.guild_id, "dashboard_message_id")

        if channel_id and message_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
            except Exception:
                pass

        database.save_setting(interaction.guild_id, "dashboard_channel_id", "")
        database.save_setting(interaction.guild_id, "dashboard_message_id", "")

        await interaction.followup.send(
            "✅ Live dashboard reset. You can now run `/setupdashboard` again.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(LiveDashboardCog(bot))
