import discord
from discord.ext import commands

import database
from utils import format_money, is_management
from ui import create_embed


def build_leaderboard_embed(guild, guild_id):
    rows = database.fetchall("""
        SELECT
            user,
            user_id,
            COUNT(*),
            COALESCE(SUM(amount_washed), 0),
            COALESCE(SUM(profit_taken), 0)
        FROM washes
        WHERE guild_id = ?
        GROUP BY user_id
        ORDER BY SUM(amount_washed) DESC
        LIMIT 10
    """, (guild_id,))

    embed = create_embed(
        "🏆 The Ledger Leaderboard",
        color=discord.Color.gold(),
        description="━━━━━━━━━━━━━━━━━━━━━━\nTop washers ranked by volume and profit.\n━━━━━━━━━━━━━━━━━━━━━━"
    )

    if not rows:
        embed.description = "No washes logged yet."
    else:
        medals = ["🥇", "🥈", "🥉"]

        for i, row in enumerate(rows):
            saved_user, user_id, washes, washed, profit = row
            medal = medals[i] if i < 3 else f"#{i + 1}"

            member = guild.get_member(int(user_id)) if guild else None
            display_name = member.display_name if member else saved_user

            embed.add_field(
                name=f"{medal}  {display_name}",
                value=(
                    f"💵 **Washed**\n"
                    f"${format_money(washed)}\n\n"
                    f"💰 **Profit**\n"
                    f"${format_money(profit)}\n\n"
                    f"🧼 **Washes**\n"
                    f"{washes}"
                ),
                inline=False
            )

            if i != len(rows) - 1:
                embed.add_field(
                    name="​",
                    value="━━━━━━━━━━━━━━━━━━━━━━",
                    inline=False
                )

    embed.set_footer(text="The Ledger • Leaderboard System")
    return embed


async def update_live_leaderboard(bot, guild_id):
    channel_id = database.get_setting(guild_id, "leaderboard_channel_id")
    message_id = database.get_setting(guild_id, "leaderboard_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return

    guild = bot.get_guild(guild_id)

    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_leaderboard_embed(guild, guild_id))
    except Exception as e:
        print(f"Live leaderboard update failed: {e}")


class LeaderboardCog(commands.Cog):
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

    @discord.app_commands.command(name="leaderboard", description="Show the top washers (one-time snapshot).")
    async def leaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.send_message(
            embed=build_leaderboard_embed(interaction.guild, interaction.guild_id)
        )

    @discord.app_commands.command(name="setupleaderboard", description="Create the permanent live leaderboard that auto-updates after every wash.")
    async def setupleaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            message = await interaction.channel.send(
                embed=build_leaderboard_embed(interaction.guild, interaction.guild_id)
            )
            database.save_setting(interaction.guild_id, "leaderboard_channel_id", str(interaction.channel.id))
            database.save_setting(interaction.guild_id, "leaderboard_message_id", str(message.id))
        except Exception as e:
            await interaction.followup.send(
                f"❌ Leaderboard setup failed: `{e}`",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            "✅ Live leaderboard created. It will update automatically after every wash.",
            ephemeral=True
        )

    @discord.app_commands.command(name="resetleaderboard", description="Reset the saved live leaderboard message.")
    async def resetleaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        channel_id = database.get_setting(interaction.guild_id, "leaderboard_channel_id")
        message_id = database.get_setting(interaction.guild_id, "leaderboard_message_id")

        if channel_id and message_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
            except Exception:
                pass

        database.save_setting(interaction.guild_id, "leaderboard_channel_id", "")
        database.save_setting(interaction.guild_id, "leaderboard_message_id", "")

        await interaction.followup.send(
            "✅ Live leaderboard reset. You can now run `/setupleaderboard` again.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(LeaderboardCog(bot))
