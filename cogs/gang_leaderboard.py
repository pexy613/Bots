import discord
from discord.ext import commands

import database
import gangs
from utils import format_money, is_management
from ui import create_embed


def build_gang_leaderboard_embed(guild_id):
    rows = database.fetchall("""
        SELECT
            gang_name,
            COUNT(*),
            COALESCE(SUM(amount_washed), 0),
            COALESCE(SUM(profit_taken), 0)
        FROM washes
        WHERE guild_id = ? AND gang_name IS NOT NULL AND TRIM(gang_name) != ''
        GROUP BY gang_name
        ORDER BY SUM(amount_washed) DESC
        LIMIT 10
    """, (guild_id,))

    embed = create_embed(
        "🏷️ Gang Wash Leaderboard",
        color=discord.Color.gold(),
        description="━━━━━━━━━━━━━━━━━━━━━━\nTop gangs ranked by total money washed.\n━━━━━━━━━━━━━━━━━━━━━━"
    )

    if not rows:
        embed.description = "No washes logged with a gang name yet."
    else:
        medals = ["🥇", "🥈", "🥉"]

        for i, row in enumerate(rows):
            gang_name, washes, washed, profit = row
            medal = medals[i] if i < 3 else f"#{i + 1}"

            embed.add_field(
                name=f"{medal}  {gang_name}",
                value=(
                    f"💵 **Washed**\n"
                    f"${format_money(washed)}\n\n"
                    f"🧼 **Washes**\n"
                    f"{washes}\n\n"
                    f"💰 **Profit**\n"
                    f"${format_money(profit)}"
                ),
                inline=False
            )

            if i != len(rows) - 1:
                embed.add_field(
                    name="​",
                    value="━━━━━━━━━━━━━━━━━━━━━━",
                    inline=False
                )

    embed.set_footer(text="The Ledger • Gang Leaderboard")
    return embed


async def update_live_gang_leaderboard(bot, guild_id):
    channel_id = database.get_setting(guild_id, "gang_leaderboard_channel_id")
    message_id = database.get_setting(guild_id, "gang_leaderboard_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return

    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_gang_leaderboard_embed(guild_id))
    except Exception as e:
        print(f"Live gang leaderboard update failed: {e}")


class GangLeaderboardCog(commands.Cog):
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

    @discord.app_commands.command(name="gangleaderboard", description="Show the top gangs by money washed (one-time snapshot).")
    async def gangleaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.send_message(
            embed=build_gang_leaderboard_embed(interaction.guild_id)
        )

    @discord.app_commands.command(name="setupgangleaderboard", description="Create the permanent live gang leaderboard that auto-updates after every wash.")
    async def setupgangleaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            message = await interaction.channel.send(
                embed=build_gang_leaderboard_embed(interaction.guild_id)
            )
            database.save_setting(interaction.guild_id, "gang_leaderboard_channel_id", str(interaction.channel.id))
            database.save_setting(interaction.guild_id, "gang_leaderboard_message_id", str(message.id))
        except Exception as e:
            await interaction.followup.send(
                f"❌ Gang leaderboard setup failed: `{e}`",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            "✅ Live gang leaderboard created. It will update automatically after every wash.",
            ephemeral=True
        )

    @discord.app_commands.command(name="resetgangleaderboard", description="Reset the saved live gang leaderboard message.")
    async def resetgangleaderboard(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        channel_id = database.get_setting(interaction.guild_id, "gang_leaderboard_channel_id")
        message_id = database.get_setting(interaction.guild_id, "gang_leaderboard_message_id")

        if channel_id and message_id:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
            except Exception:
                pass

        database.save_setting(interaction.guild_id, "gang_leaderboard_channel_id", "")
        database.save_setting(interaction.guild_id, "gang_leaderboard_message_id", "")

        await interaction.followup.send(
            "✅ Live gang leaderboard reset. You can now run `/setupgangleaderboard` again.",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="gangalias",
        description="Make a shortcut resolve to a gang's full name (e.g. 'cfc' -> 'Cash Flow Cartel')."
    )
    @discord.app_commands.describe(
        alias="The shortcut people might type (e.g. cfc)",
        gang_name="The full gang name it should resolve to"
    )
    async def gangalias(self, interaction: discord.Interaction, alias: str, gang_name: str):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        canonical = gangs.add_alias(interaction.guild_id, alias, gang_name)
        await interaction.followup.send(
            f"✅ `{alias}` will now resolve to **{canonical}**.",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="gangmerge",
        description="Fold an existing gang name variant (typo/case/spacing duplicate) into another."
    )
    @discord.app_commands.describe(
        from_name="The duplicate/incorrect gang name currently in the logs",
        into_name="The correct gang name to merge it into"
    )
    async def gangmerge(self, interaction: discord.Interaction, from_name: str, into_name: str):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        canonical = gangs.merge_gang(interaction.guild_id, from_name, into_name)
        await update_live_gang_leaderboard(self.bot, interaction.guild_id)
        await interaction.followup.send(
            f"✅ All washes logged under `{from_name}` are now credited to **{canonical}**.",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="gangremove",
        description="Remove a gang from the wash logger's picker list (past wash history is kept)."
    )
    @discord.app_commands.describe(gang_name="The gang to remove from the picker list")
    async def gangremove(self, interaction: discord.Interaction, gang_name: str):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        removed = gangs.remove_gang(interaction.guild_id, gang_name)
        if removed is None:
            await interaction.followup.send(
                f"❌ No registered gang matching `{gang_name}` was found.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ **{removed}** removed from the gang picker list. Past wash history logged under it is unaffected.",
            ephemeral=True
        )

    @discord.app_commands.command(name="ganglist", description="List all registered gangs and shortcut aliases.")
    async def ganglist(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            return

        known = gangs.list_known_gangs(interaction.guild_id, limit=25)
        aliases = gangs.list_aliases(interaction.guild_id)

        embed = create_embed("🏷️ Registered Gangs", color=discord.Color.blurple())
        embed.add_field(
            name="Gangs",
            value="\n".join(f"• {name}" for name in known) if known else "No gangs registered yet.",
            inline=False
        )
        embed.add_field(
            name="Aliases",
            value="\n".join(f"• `{alias}` → {canonical}" for alias, canonical in aliases) if aliases else "No aliases registered yet.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(GangLeaderboardCog(bot))
