from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

import database
from utils import format_money, is_management
from ui import create_embed


EASTERN = ZoneInfo("America/New_York")


def get_week_start_est():
    now_est = datetime.now(EASTERN)
    monday_est = now_est - timedelta(days=now_est.weekday())
    return monday_est.replace(hour=0, minute=0, second=0, microsecond=0)


def get_next_week_start_est():
    return get_week_start_est() + timedelta(days=7)


def get_week_start_utc():
    return get_week_start_est().astimezone(timezone.utc)


def get_reset_countdown():
    now_est = datetime.now(EASTERN)
    next_reset = get_next_week_start_est()
    remaining = next_reset - now_est

    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    return f"{days}d {hours}h {minutes}m"


def get_week_key():
    return get_week_start_est().strftime("%Y-%m-%d")


def get_weekly_total(guild_id):
    week_start = get_week_start_utc().strftime("%Y-%m-%d %H:%M:%S")

    row = database.fetchone("""
        SELECT COALESCE(SUM(amount_washed), 0), COUNT(*)
        FROM washes
        WHERE guild_id = ? AND timestamp >= ?
    """, (guild_id, week_start))

    if not row:
        return 0, 0

    return row[0], row[1]


def progress_bar(percent):
    filled = int(percent / 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty


def goal_color(percent):
    if percent >= 100:
        return discord.Color.purple()
    if percent >= 80:
        return discord.Color.green()
    if percent >= 50:
        return discord.Color.gold()
    return discord.Color.red()


def build_goal_embed(guild_id):
    goal = database.get_setting(guild_id, "weekly_goal")
    goal = int(goal) if goal else 0

    washed, washes = get_weekly_total(guild_id)
    remaining = max(goal - washed, 0)

    percent = 0
    if goal > 0:
        percent = min(int((washed / goal) * 100), 100)

    completed = goal > 0 and washed >= goal

    title = "🎯 WEEKLY MONEY WASH GOAL"
    if completed:
        title = "🎉 WEEKLY GOAL COMPLETED"

    status_text = "**Goal reached. Great work everyone.**" if completed else "**Progress updates automatically from wash logs.**"
    embed = create_embed(
        title,
        color=goal_color(percent),
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_text}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    )

    embed.add_field(
        name="🎯 Goal",
        value=f"**${format_money(goal)}**",
        inline=False
    )

    embed.add_field(
        name="💵 Washed This Week",
        value=f"**${format_money(washed)}**",
        inline=False
    )

    embed.add_field(
        name="📊 Progress",
        value=f"`{progress_bar(percent)}` **{percent}%**",
        inline=False
    )

    embed.add_field(
        name="💰 Remaining",
        value=f"**${format_money(remaining)}**",
        inline=True
    )

    embed.add_field(
        name="🧼 Washes This Week",
        value=f"**{washes}**",
        inline=True
    )

    embed.add_field(
        name="⏰ Resets In",
        value=f"**{get_reset_countdown()}**",
        inline=True
    )

    embed.set_footer(text="The Ledger • Resets every Monday at 12:00 AM EST")

    return embed


async def send_goal_celebration(bot, channel, guild_id, goal, washed):
    week_key = get_week_key()
    celebrated_key = database.get_setting(guild_id, "weekly_goal_celebrated_week")

    if celebrated_key == week_key:
        return

    database.save_setting(guild_id, "weekly_goal_celebrated_week", week_key)

    embed = create_embed(
        "🎉 WEEKLY GOAL ACHIEVED",
        color=discord.Color.purple(),
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"The crew has reached this week's goal of **${format_money(goal)}**.\n\n"
            f"Current weekly total: **${format_money(washed)}**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Great work everyone. 💰"
        ),
        footer="The Ledger • Weekly Goal System"
    )

    await channel.send(embed=embed)


async def update_goal_dashboard(bot, guild_id):
    channel_id = database.get_setting(guild_id, "goal_channel_id")
    message_id = database.get_setting(guild_id, "goal_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(message_id))
        await message.edit(embed=build_goal_embed(guild_id))

        goal = database.get_setting(guild_id, "weekly_goal")
        goal = int(goal) if goal else 0

        washed, washes = get_weekly_total(guild_id)

        if goal > 0 and washed >= goal:
            await send_goal_celebration(bot, channel, guild_id, goal, washed)

    except Exception as e:
        print(f"Goal dashboard update failed: {e}")


class GoalsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="setgoal", description="Set the weekly money wash goal.")
    async def setgoal(self, interaction: discord.Interaction, amount: int):
        if not is_management(interaction.user):
            await interaction.response.send_message(
                "❌ Only Management can use this command.",
                ephemeral=True
            )
            return

        database.save_setting(interaction.guild_id, "weekly_goal", str(amount))
        await update_goal_dashboard(self.bot, interaction.guild_id)

        await interaction.response.send_message(
            f"✅ Weekly goal set to ${format_money(amount)}.",
            ephemeral=True
        )

    @discord.app_commands.command(name="setupgoal", description="Create the permanent weekly goal dashboard in this channel.")
    async def setupgoal(self, interaction: discord.Interaction):
        if not is_management(interaction.user):
            await interaction.response.send_message(
                "❌ Only Management can use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        old_channel_id = database.get_setting(interaction.guild_id, "goal_channel_id")
        old_message_id = database.get_setting(interaction.guild_id, "goal_message_id")

        if old_channel_id and old_message_id:
            try:
                old_channel = self.bot.get_channel(int(old_channel_id))
                if old_channel:
                    old_message = await old_channel.fetch_message(int(old_message_id))
                    await old_message.delete()
            except Exception:
                pass

        message = await interaction.channel.send(embed=build_goal_embed(interaction.guild_id))

        database.save_setting(interaction.guild_id, "goal_channel_id", str(interaction.channel.id))
        database.save_setting(interaction.guild_id, "goal_message_id", str(message.id))

        await interaction.followup.send(
            "✅ Weekly goal dashboard created here and synced to wash logs.",
            ephemeral=True
        )

    @discord.app_commands.command(name="showgoal", description="Show the current weekly goal progress here.")
    async def showgoal(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_goal_embed(interaction.guild_id))


async def setup(bot):
    await bot.add_cog(GoalsCog(bot))