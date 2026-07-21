import discord
from discord.ext import commands

import database
from utils import is_management
from ui import create_embed
from cogs.wash import WashSelectionView


class LogWashPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Wash Logger",
        emoji="💵",
        style=discord.ButtonStyle.blurple,
        custom_id="log_wash_button_persistent_v2"
    )
    async def log_wash_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_embed(
            "🧼 Money Wash Logger",
            color=discord.Color.blurple(),
            description="Use the menu below to log your money wash."
        )
        await interaction.response.send_message(embed=embed, view=WashSelectionView(), ephemeral=True)


async def move_log_panel_to_bottom(channel, guild_id):
    old_id = database.get_setting(guild_id, "log_panel_message_id")
    if old_id:
        try:
            old_message = await channel.fetch_message(int(old_id))
            await old_message.delete()
        except Exception:
            pass

    try:
        async for message in channel.history(limit=50):
            if message.author.bot and message.embeds:
                embed = message.embeds[0]
                if embed.title == "🧼 Money Wash Panel":
                    try:
                        await message.delete()
                    except Exception:
                        pass
    except Exception:
        pass

    embed = create_embed(
        "🧼 Money Wash Panel",
        color=discord.Color.blurple(),
        description="Use the button below to log a wash.\n\nDropdown-based logging is now built in for a cleaner experience."
    )

    new_message = await channel.send(embed=embed, view=LogWashPanel())
    database.save_setting(guild_id, "log_panel_message_id", str(new_message.id))


class PanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(LogWashPanel())

    @discord.app_commands.command(name="setuplogpanel", description="Create the Log Wash button panel.")
    async def setuplogpanel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not is_management(interaction.user):
            await interaction.followup.send(
                "❌ Only Management can set this up.",
                ephemeral=True
            )
            return

        await move_log_panel_to_bottom(interaction.channel, interaction.guild_id)

        await interaction.followup.send(
            "✅ Log Wash panel created.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PanelCog(bot))