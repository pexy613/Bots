import asyncio
import time
import re
import os
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_client, Client

import database
from utils import format_money, can_manage
from ui import create_embed
from cogs.live_dashboard import update_live_dashboard
from cogs.leaderboard import update_live_leaderboard
from cogs.gang_leaderboard import update_live_gang_leaderboard
from cogs.combined_panels import update_live_combined_dashboard, update_live_combined_leaderboard

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

log = logging.getLogger("wash")


# --- Supabase mirror (Laundering_bot.transactions) -------------------------
# Best-effort write: washes.db above remains the bot's source of truth for
# live logic (dashboards, leaderboards, delete button, etc). This call mirrors
# each logged wash into Supabase and never raises into the caller if the
# network call fails.

def supabase_log_transaction(discord_user_id: int, discord_username: str, amount_processed: float,
                              fee_percent: float, net_profit: float, gang_name: str | None, logged_at: str) -> None:
    try:
        supabase.schema("Laundering_bot").table("transactions").insert({
            "discord_user_id": discord_user_id,
            "discord_username": discord_username,
            "amount_processed": amount_processed,
            "fee_percent": fee_percent,
            "net_profit": net_profit,
            "gang_name": gang_name,
            "logged_at": logged_at,
        }).execute()
    except Exception:
        log.exception("Supabase log_transaction failed for %s", discord_user_id)


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
        await update_live_gang_leaderboard(interaction.client, interaction.guild_id)
        await update_live_combined_dashboard(interaction.client, interaction.guild_id)
        await update_live_combined_leaderboard(interaction.client, interaction.guild_id)

        from cogs.goals import update_goal_dashboard
        await update_goal_dashboard(interaction.client, interaction.guild_id)


COMMISSION_PERCENTAGES = (5, 8, 10, 15, 20, 25, 30)

AMOUNT_BLOCKS = (
    (0, "$1M – $10M"),
    (10, "$11M – $20M"),
    (20, "$21M – $30M"),
    (30, "$31M – $40M"),
    (40, "$41M – $50M"),
)


class AmountBlockSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=str(block_start), emoji="💸")
            for block_start, label in AMOUNT_BLOCKS
        ]
        super().__init__(
            placeholder="Step 1: Choose amount range",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="wash_amount_block_select",
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        block_start = int(self.values[0])
        self.view.amount_washed = None
        self.view.set_amount_block(block_start)
        label = next(label for start, label in AMOUNT_BLOCKS if start == block_start)
        self.placeholder = f"Range: {label}"
        await interaction.response.edit_message(embed=self.view.build_status_embed(), view=self.view)


class AmountExactSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Step 2: Pick a range above first",
            options=[discord.SelectOption(label="Pick a range above first", value="placeholder")],
            min_values=1,
            max_values=1,
            custom_id="wash_amount_exact_select",
            row=1,
            disabled=True
        )

    async def callback(self, interaction: discord.Interaction):
        amount_value = int(self.values[0])
        self.view.amount_washed = amount_value
        self.placeholder = f"Amount: ${format_money(amount_value)}"
        await interaction.response.edit_message(embed=self.view.build_status_embed(), view=self.view)


class CommissionButton(discord.ui.Button):
    def __init__(self, percentage: float, row: int):
        super().__init__(
            label=f"{percentage:.0f}%",
            style=discord.ButtonStyle.secondary,
            custom_id=f"wash_commission_button_{percentage:.0f}",
            row=row
        )
        self.percentage = percentage

    async def callback(self, interaction: discord.Interaction):
        self.view.percentage_taken = self.percentage
        self.view.refresh_commission_buttons()
        await interaction.response.edit_message(embed=self.view.build_status_embed(), view=self.view)


class GangModal(discord.ui.Modal, title="Set Gang"):
    def __init__(self, wash_view: "WashSelectionView"):
        super().__init__()
        self.wash_view = wash_view
        self.gang_input = discord.ui.TextInput(
            label="Gang name",
            placeholder="e.g. Vagos",
            max_length=100,
            required=True,
            default=wash_view.gang_name or None
        )
        self.add_item(self.gang_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.wash_view.gang_name = str(self.gang_input.value).strip()
        self.wash_view.refresh_gang_button()
        await interaction.response.edit_message(embed=self.wash_view.build_status_embed(), view=self.wash_view)


class GangButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Set Gang (optional)",
            emoji="🏷️",
            style=discord.ButtonStyle.secondary,
            custom_id="wash_gang_button",
            row=3
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GangModal(self.view))


class LogWashButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Log Wash",
            emoji="🧼",
            style=discord.ButtonStyle.green,
            custom_id="wash_submit_button",
            row=3
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.do_submit(interaction)


class WashSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.amount_washed = None
        self.percentage_taken = None
        self.gang_name = None
        self._submission_in_progress = False
        self._submit_lock = asyncio.Lock()

        self.amount_exact_select = AmountExactSelect()

        self.add_item(AmountBlockSelect())
        self.add_item(self.amount_exact_select)

        for percentage in COMMISSION_PERCENTAGES[:5]:
            self.add_item(CommissionButton(percentage, row=2))
        for percentage in COMMISSION_PERCENTAGES[5:]:
            self.add_item(CommissionButton(percentage, row=3))

        self.add_item(GangButton())
        self.add_item(LogWashButton())

    def set_amount_block(self, block_start: int):
        options = [
            discord.SelectOption(
                label=f"${(block_start + m) * 1_000_000:,}",
                value=str((block_start + m) * 1_000_000),
                emoji="💸"
            )
            for m in range(1, 11)
        ]
        self.amount_exact_select.options = options
        self.amount_exact_select.disabled = False
        self.amount_exact_select.placeholder = "Step 2: Choose exact amount"

    def refresh_commission_buttons(self):
        for child in self.children:
            if isinstance(child, CommissionButton):
                child.style = (
                    discord.ButtonStyle.success
                    if child.percentage == self.percentage_taken
                    else discord.ButtonStyle.secondary
                )

    def refresh_gang_button(self):
        for child in self.children:
            if isinstance(child, GangButton):
                if self.gang_name:
                    child.label = f"Gang: {self.gang_name}"[:80]
                    child.style = discord.ButtonStyle.success
                else:
                    child.label = "Set Gang (optional)"
                    child.style = discord.ButtonStyle.secondary

    def build_status_embed(self) -> discord.Embed:
        embed = create_embed(
            "🧼 Money Wash Logger",
            color=discord.Color.blurple(),
            description="Use the menus and buttons below to log your money wash — nothing is submitted until you press Log Wash."
        )
        embed.add_field(
            name="💵 Amount",
            value=f"**${format_money(self.amount_washed)}**" if self.amount_washed is not None else "*Not set*",
            inline=True
        )
        embed.add_field(
            name="📉 Commission",
            value=f"**{self.percentage_taken:.0f}%**" if self.percentage_taken is not None else "*Not set*",
            inline=True
        )
        embed.add_field(
            name="🏷️ Gang",
            value=f"**{self.gang_name}**" if self.gang_name else "*Not set (optional)*",
            inline=True
        )
        return embed

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

    async def do_submit(self, interaction: discord.Interaction):
        if self._submission_in_progress:
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

        if not self.begin_submission():
            await interaction.response.send_message(
                "⏳ This wash is already being logged. Please wait a moment.",
                ephemeral=True
            )
            return

        async with self._submit_lock:
            amount_washed = self.amount_washed
        percentage_taken = self.percentage_taken
        gang_name = self.gang_name
        profit_taken = int(amount_washed * (percentage_taken / 100))

        conn = database.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO washes
            (guild_id, user, user_id, amount_washed, percentage_taken, profit_taken, gang_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction.guild_id,
            str(interaction.user),
            interaction.user.id,
            amount_washed,
            percentage_taken,
            profit_taken,
            gang_name
        ))

        wash_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            embed=create_embed(
                "✅ Wash Logged",
                color=discord.Color.green(),
                description=f"Wash #{wash_id} has been recorded below."
            ),
            view=self
        )

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

        if gang_name:
            embed.add_field(
                name="🏷️ Gang",
                value=f"**{gang_name}**",
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
        await interaction.followup.send(embed=embed, view=delete_view)

        supabase_log_transaction(
            interaction.user.id,
            str(interaction.user),
            amount_washed,
            percentage_taken,
            profit_taken,
            gang_name,
            datetime.now(timezone.utc).isoformat(),
        )

        await update_live_dashboard(interaction.client, interaction.guild_id)
        await update_live_leaderboard(interaction.client, interaction.guild_id)
        await update_live_gang_leaderboard(interaction.client, interaction.guild_id)
        await update_live_combined_dashboard(interaction.client, interaction.guild_id)
        await update_live_combined_leaderboard(interaction.client, interaction.guild_id)

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