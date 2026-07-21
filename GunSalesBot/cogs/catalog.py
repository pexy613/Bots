import discord
from discord import app_commands
from discord.ext import commands

from ..config import DEFAULT_DISCOUNT_PERCENT, Emoji
from ..utils.layouts import catalog_view, error_view


class Catalog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    catalog_group = app_commands.Group(name="catalog", description="Manage and view the weapon price catalog")

    async def gun_autocomplete(self, interaction: discord.Interaction, current: str):
        names = await self.bot.db.gun_name_choices(str(interaction.guild_id), current)
        return [app_commands.Choice(name=n, value=n) for n in names]

    @catalog_group.command(name="view", description="View the current weapon price catalog")
    async def view(self, interaction: discord.Interaction):
        guns = await self.bot.db.list_guns(str(interaction.guild_id))
        if not guns:
            await interaction.response.send_message(
                view=error_view("No weapons in the catalog yet. Use `/catalog add` to add one."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(view=catalog_view(interaction.guild.name, guns))

    @catalog_group.command(name="add", description="[Admin] Add a weapon to the catalog")
    @app_commands.describe(
        name="Weapon name",
        price="Full price",
        discount_percent="Ally/discounted price, as a percent off (default 25)",
        category="Category, e.g. Pistol, Rifle, Shotgun, Sniper",
        emoji="Emoji shown next to the weapon",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(
        self,
        interaction: discord.Interaction,
        name: str,
        price: app_commands.Range[int, 1],
        discount_percent: app_commands.Range[float, 0, 100] = DEFAULT_DISCOUNT_PERCENT,
        category: str = "Uncategorized",
        emoji: str = "🔫",
    ):
        existing = await self.bot.db.get_gun(str(interaction.guild_id), name)
        if existing:
            await interaction.response.send_message(
                view=error_view(f"**{name}** is already in the catalog. Use `/catalog edit` instead."),
                ephemeral=True,
            )
            return
        await self.bot.db.add_gun(
            guild_id=str(interaction.guild_id),
            name=name,
            price=price,
            discount_percent=discount_percent,
            category=category,
            emoji=emoji,
        )
        await interaction.response.send_message(f"{Emoji.GUN} Added **{name}** to the catalog.")

    @catalog_group.command(name="edit", description="[Admin] Edit a weapon's catalog entry")
    @app_commands.describe(
        name="Weapon to edit",
        price="New full price",
        discount_percent="New ally discount percent",
        category="New category",
        emoji="New emoji",
    )
    @app_commands.autocomplete(name=gun_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit(
        self,
        interaction: discord.Interaction,
        name: str,
        price: app_commands.Range[int, 1] = None,
        discount_percent: app_commands.Range[float, 0, 100] = None,
        category: str = None,
        emoji: str = None,
    ):
        fields = {
            k: v
            for k, v in {
                "price": price,
                "discount_percent": discount_percent,
                "category": category,
                "emoji": emoji,
            }.items()
            if v is not None
        }
        if not fields:
            await interaction.response.send_message(
                view=error_view("Provide at least one field to update."), ephemeral=True
            )
            return
        updated = await self.bot.db.edit_gun(str(interaction.guild_id), name, **fields)
        if not updated:
            await interaction.response.send_message(
                view=error_view(f"No weapon named **{name}** found."), ephemeral=True
            )
            return
        await interaction.response.send_message(f"{Emoji.GUN} Updated **{name}**.")

    @catalog_group.command(name="remove", description="[Admin] Remove a weapon from the catalog")
    @app_commands.describe(name="Weapon to remove")
    @app_commands.autocomplete(name=gun_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, name: str):
        removed = await self.bot.db.remove_gun(str(interaction.guild_id), name)
        if not removed:
            await interaction.response.send_message(
                view=error_view(f"No weapon named **{name}** found."), ephemeral=True
            )
            return
        await interaction.response.send_message(f"🗑️ Removed **{name}** from the catalog.")

    @add.error
    @edit.error
    @remove.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                view=error_view("You need the **Manage Server** permission to do that."),
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Catalog(bot))
