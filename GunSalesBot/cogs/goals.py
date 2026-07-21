from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.layouts import error_view, goal_list_view, goal_view
from utils.formatting import money


async def update_live_goal(bot: commands.Bot, guild: discord.Guild) -> None:
    """Refreshes the active goal's live panel (if any) after a sale changes."""
    goal = await bot.db.get_active_goal(str(guild.id))
    if not goal or not goal["panel_channel_id"] or not goal["panel_message_id"]:
        return

    channel = guild.get_channel(int(goal["panel_channel_id"]))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(goal["panel_message_id"]))
    except (discord.NotFound, discord.Forbidden):
        return

    current = await bot.db.goal_current_amount(goal)
    try:
        await message.edit(view=goal_view(goal, current))
    except discord.HTTPException:
        pass


class Goals(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    goal_group = app_commands.Group(name="goal", description="Set and track a weapon sales goal")

    @goal_group.command(
        name="set", description="[Admin] Start a weapon sales goal and post a live-tracking panel"
    )
    @app_commands.describe(
        target="Target dollar amount to hit in weapon sales",
        deadline_days="Optional: end the goal after this many days",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_goal(
        self,
        interaction: discord.Interaction,
        target: app_commands.Range[int, 1],
        deadline_days: app_commands.Range[int, 1] = None,
    ):
        end_at = None
        if deadline_days:
            end_at = (datetime.now(timezone.utc) + timedelta(days=deadline_days)).isoformat()

        await self.bot.db.create_goal(
            guild_id=str(interaction.guild_id),
            name="Weapon Sales Goal",
            target_amount=target,
            metric="washed",
            end_at=end_at,
            created_by=str(interaction.user.id),
        )
        goal = await self.bot.db.get_active_goal(str(interaction.guild_id))
        current = await self.bot.db.goal_current_amount(goal)
        await interaction.response.send_message(view=goal_view(goal, current))
        message = await interaction.original_response()
        await self.bot.db.set_goal_panel(goal["id"], str(interaction.channel_id), str(message.id))

    @goal_group.command(name="progress", description="Show progress on the active weapon sales goal")
    async def progress(self, interaction: discord.Interaction):
        goal = await self.bot.db.get_active_goal(str(interaction.guild_id))
        if not goal:
            await interaction.response.send_message(
                view=error_view("No active goal. An admin can set one with `/goal set`."),
                ephemeral=True,
            )
            return
        current = await self.bot.db.goal_current_amount(goal)
        await interaction.response.send_message(view=goal_view(goal, current))

    @goal_group.command(name="end", description="[Admin] End the active weapon sales goal")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end(self, interaction: discord.Interaction):
        goal = await self.bot.db.get_active_goal(str(interaction.guild_id))
        if not goal:
            await interaction.response.send_message(
                view=error_view("No active goal to end."), ephemeral=True
            )
            return
        current = await self.bot.db.goal_current_amount(goal)
        await self.bot.db.end_goal(goal["id"])

        if goal["panel_channel_id"] and goal["panel_message_id"]:
            channel = interaction.guild.get_channel(int(goal["panel_channel_id"]))
            if channel:
                try:
                    message = await channel.fetch_message(int(goal["panel_message_id"]))
                    ended_goal = {
                        "target_amount": goal["target_amount"],
                        "active": 0,
                        "end_at": goal["end_at"],
                    }
                    await message.edit(view=goal_view(ended_goal, current))
                except (discord.NotFound, discord.Forbidden):
                    pass

        await interaction.response.send_message(f"🏁 Goal ended — final total: **{money(current)}**.")

    @goal_group.command(name="list", description="Show recent weapon sales goals")
    async def list_goals(self, interaction: discord.Interaction):
        goals = await self.bot.db.list_goals(str(interaction.guild_id))
        if not goals:
            await interaction.response.send_message(
                view=error_view("No goals have been set yet."), ephemeral=True
            )
            return
        await interaction.response.send_message(view=goal_list_view(goals))

    @set_goal.error
    @end.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                view=error_view("You need the **Manage Server** permission to do that."),
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Goals(bot))
