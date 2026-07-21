import asyncio
import time
import re
import discord
from discord.ext import commands

import database
from utils import format_money, can_manage
from ui import create_embed
from cogs.live_dashboard import update_live_dashboard
from cogs.leaderboard import update_live_leaderboard


class DeleteWashButton(discord.ui.DynamicItem[discord.ui.Button], template=r"delete_wash:(?P<wash_id>[0-9]+)"):
    def __init__(self, wash_id: int):
        super().__init__(
            discord.ui.Button(
                emoji="❌",
                style=discord.ButtonStyle.danger,
                custom_id=f"delete_wash:{wash_id}"
            )
        )
        self.wash_id = wash_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match, /):
        return cls(int(match["wash_id"]))

    async def callback(self, interaction: discord.Interaction):
        row = database.fetchone(
            "SELECT id, user_id FROM washes WHERE id = ? AND guild_id = ?",
            (self.wash_id, interaction.guild_id)
        )
        if not row:
            await interaction.response.send_message(
                f"❌ Wash #{self.wash_id} was already deleted.",
                ephemeral=True
            )
            return

        wash_id, owner_id = row
        if not can_manage(interaction.user) and interaction.user.id != owner_id:
            await interaction.response.send_message(
                "❌ Only the person who logged this wash, or an admin/management member, can delete it.",
                ephemeral=True
            )
            return

        database.execute(
            "DELETE FROM washes WHERE id = ? AND guild_id = ?",
            (self.wash_id, interaction.guild_id)
        )

        await interaction.response.send_message(
            f"✅ Wash #{wash_id} deleted.",
            ephemeral=True
        )

        try:
            await interaction.message.delete()
        except Exception:
            pass

        await update_live_dashboard(interaction.client, interaction.guild_id)
        await update_live_leaderboard(interaction.client, interaction.guild_id)

        from cogs.goals import update_goal_dashboard
        await update_goal_dashboard(interaction.client, interaction.guild_id)


class AmountSelect(discord.ui.Select):
    def __init__(self, placeholder: str, options, custom_id: str):
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        amount_value = int(self.values[0])
        self.view.amount_washed = amount_value
        self.placeholder = f"Amount: ${format_money(amount_value)}"
        await interaction.response.edit_message(content=f"✅ Amount set to ${format_money(amount_value)}")


class PercentageSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose commission percentage",
            options=[
                discord.SelectOption(label="5%", value="5"),
                discord.SelectOption(label="10%", value="10"),
                discord.SelectOption(label="15%", value="15"),
                discord.SelectOption(label="20%", value="20"),
                discord.SelectOption(label="25%", value="25"),
                discord.SelectOption(label="30%", value="30")
            ],
            min_values=1,
            max_values=1,
            custom_id="wash_percentage_select"
        )

    async def callback(self, interaction: discord.Interaction):
        percentage_value = float(self.values[0])
        self.view.percentage_taken = percentage_value
        self.placeholder = f"Commission: {percentage_value:.0f}%"
        await interaction.response.edit_message(content=f"✅ Commission set to {percentage_value:.0f}%")


class WashSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.amount_washed = None
        self.percentage_taken = None
        self._submission_in_progress = False
        self._submit_lock = asyncio.Lock()

        amount_options_1 = [
            discord.SelectOption(label="$1,000,000", value="1000000", emoji="💸"),
            discord.SelectOption(label="$2,000,000", value="2000000", emoji="💸"),
            discord.SelectOption(label="$3,000,000", value="3000000", emoji="💸"),
            discord.SelectOption(label="$4,000,000", value="4000000", emoji="💸"),
            discord.SelectOption(label="$5,000,000", value="5000000", emoji="💸"),
            discord.SelectOption(label="$6,000,000", value="6000000", emoji="💸"),
            discord.SelectOption(label="$7,000,000", value="7000000", emoji="💸"),
            discord.SelectOption(label="$8,000,000", value="8000000", emoji="💸"),
            discord.SelectOption(label="$9,000,000", value="9000000", emoji="💸"),
            discord.SelectOption(label="$10,000,000", value="10000000", emoji="💸"),
            discord.SelectOption(label="$11,000,000", value="11000000", emoji="💸"),
            discord.SelectOption(label="$12,000,000", value="12000000", emoji="💸"),
            discord.SelectOption(label="$13,000,000", value="13000000", emoji="💸"),
            discord.SelectOption(label="$14,000,000", value="14000000", emoji="💸"),
            discord.SelectOption(label="$15,000,000", value="15000000", emoji="💸"),
            discord.SelectOption(label="$16,000,000", value="16000000", emoji="💸"),
            discord.SelectOption(label="$17,000,000", value="17000000", emoji="💸"),
            discord.SelectOption(label="$18,000,000", value="18000000", emoji="💸"),
            discord.SelectOption(label="$19,000,000", value="19000000", emoji="💸"),
            discord.SelectOption(label="$20,000,000", value="20000000", emoji="💸"),
            discord.SelectOption(label="$21,000,000", value="21000000", emoji="💸"),
            discord.SelectOption(label="$22,000,000", value="22000000", emoji="💸"),
            discord.SelectOption(label="$23,000,000", value="23000000", emoji="💸"),
            discord.SelectOption(label="$24,000,000", value="24000000", emoji="💸"),
            discord.SelectOption(label="$25,000,000", value="25000000", emoji="💸")
        ]

        amount_options_2 = [
            discord.SelectOption(label="$26,000,000", value="26000000", emoji="💸"),
            discord.SelectOption(label="$27,000,000", value="27000000", emoji="💸"),
            discord.SelectOption(label="$28,000,000", value="28000000", emoji="💸"),
            discord.SelectOption(label="$29,000,000", value="29000000", emoji="💸"),
            discord.SelectOption(label="$30,000,000", value="30000000", emoji="💸"),
            discord.SelectOption(label="$31,000,000", value="31000000", emoji="💸"),
            discord.SelectOption(label="$32,000,000", value="32000000", emoji="💸"),
            discord.SelectOption(label="$33,000,000", value="33000000", emoji="💸"),
            discord.SelectOption(label="$34,000,000", value="34000000", emoji="💸"),
            discord.SelectOption(label="$35,000,000", value="35000000", emoji="💸"),
            discord.SelectOption(label="$36,000,000", value="36000000", emoji="💸"),
            discord.SelectOption(label="$37,000,000", value="37000000", emoji="💸"),
            discord.SelectOption(label="$38,000,000", value="38000000", emoji="💸"),
            discord.SelectOption(label="$39,000,000", value="39000000", emoji="💸"),
            discord.SelectOption(label="$40,000,000", value="40000000", emoji="💸"),
            discord.SelectOption(label="$41,000,000", value="41000000", emoji="💸"),
            discord.SelectOption(label="$42,000,000", value="42000000", emoji="💸"),
            discord.SelectOption(label="$43,000,000", value="43000000", emoji="💸"),
            discord.SelectOption(label="$44,000,000", value="44000000", emoji="💸"),
            discord.SelectOption(label="$45,000,000", value="45000000", emoji="💸"),
            discord.SelectOption(label="$46,000,000", value="46000000", emoji="💸"),
            discord.SelectOption(label="$47,000,000", value="47000000", emoji="💸"),
            discord.SelectOption(label="$48,000,000", value="48000000", emoji="💸"),
            discord.SelectOption(label="$49,000,000", value="49000000", emoji="💸"),
            discord.SelectOption(label="$50,000,000", value="50000000", emoji="💸")
        ]

        self.add_item(
            AmountSelect(
                placeholder="Choose amount washed (1M–25M)",
                options=amount_options_1,
                custom_id="wash_amount_select_1"
            )
        )
        self.add_item(
            AmountSelect(
                placeholder="Choose amount washed (26M–50M)",
                options=amount_options_2,
                custom_id="wash_amount_select_2"
            )
        )
        self.add_item(PercentageSelect())

    def begin_submission(self) -> bool:
        if self._submission_in_progress:
            return False

        self._submission_in_progress = True
        for child in self.children:
            child.disabled = True
        self.stop()
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._submission_in_progress:
            await interaction.response.send_message(
                "⏳ This wash is already being logged. Please wait a moment.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Log Wash",
        emoji="🧼",
        style=discord.ButtonStyle.green,
        custom_id="wash_submit_button"
    )
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.begin_submission():
            await interaction.response.send_message(
                "⏳ This wash is already being logged. Please wait a moment.",
                ephemeral=True
            )
            return

        if self.amount_washed is None or self.percentage_taken is None:
            await interaction.response.send_message(
                "❌ Choose both an amount and a commission percentage first.",
                ephemeral=True
            )
            return

        async with self._submit_lock:
            amount_washed = self.amount_washed
        percentage_taken = self.percentage_taken
        profit_taken = int(amount_washed * (percentage_taken / 100))

        conn = database.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO washes
            (guild_id, user, user_id, amount_washed, percentage_taken, profit_taken)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            interaction.guild_id,
            str(interaction.user),
            interaction.user.id,
            amount_washed,
            percentage_taken,
            profit_taken
        ))

        wash_id = cursor.lastrowid
        conn.commit()
        conn.close()

        embed = create_embed(
            "🧾 MONEY WASH RECEIPT",
            color=discord.Color.blurple(),
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**🆔 Wash ID:** #{wash_id}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
        )

        embed.add_field(
            name="💵 Amount Washed",
            value=f"**${format_money(amount_washed)}**",
            inline=True
        )

        embed.add_field(
            name="📉 Commission",
            value=f"**{percentage_taken:.0f}%**",
            inline=True
        )

        embed.add_field(
            name="💰 Profit Earned",
            value=f"**${format_money(profit_taken)}**",
            inline=True
        )

        embed.add_field(
            name="👤 Logged By",
            value=f"**{interaction.user.display_name}**\n{interaction.user.mention}",
            inline=True
        )

        embed.add_field(
            name="🕒 Logged At",
            value=f"<t:{int(time.time())}:f>",
            inline=True
        )

        embed.set_footer(text="The Ledger • Auto-synced to dashboard")

        delete_view = discord.ui.View(timeout=None)
        delete_view.add_item(DeleteWashButton(wash_id))
        await interaction.response.send_message(embed=embed, view=delete_view)

        await update_live_dashboard(interaction.client, interaction.guild_id)
        await update_live_leaderboard(interaction.client, interaction.guild_id)

        from cogs.goals import update_goal_dashboard
        await update_goal_dashboard(interaction.client, interaction.guild_id)

        from cogs.panel import move_log_panel_to_bottom
        await move_log_panel_to_bottom(interaction.channel, interaction.guild_id)


class WashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_dynamic_items(DeleteWashButton)


async def setup(bot):
    await bot.add_cog(WashCog(bot))