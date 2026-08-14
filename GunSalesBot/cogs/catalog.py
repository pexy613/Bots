import discord
from discord import app_commands
from discord.ext import commands

from ..config import DEFAULT_DISCOUNT_PERCENT, Emoji
from ..seed_data import DEFAULT_CATALOG
from ..supabase_mirror import supabase_upsert_gun
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
        supabase_upsert_gun(await self.bot.db.get_gun_any(str(interaction.guild_id), name))
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
        supabase_upsert_gun(await self.bot.db.get_gun_any(str(interaction.guild_id), name))
        await interaction.response.send_message(f"{Emoji.GUN} Updated **{name}**.")

    @catalog_group.command(
        name="sync-defaults",
        description="[Admin] Sync this server's catalog to the bot's current default price list",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_defaults(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        existing = {g["name"].lower(): g for g in await self.bot.db.list_guns(guild_id)}
        target_names = {item["name"].lower() for item in DEFAULT_CATALOG}

        added, updated, removed = [], [], []
        for item in DEFAULT_CATALOG:
            row = existing.get(item["name"].lower())
            if row is None:
                await self.bot.db.add_gun(
                    guild_id=guild_id,
                    name=item["name"],
                    price=item["price"],
                    discount_percent=DEFAULT_DISCOUNT_PERCENT,
                    category=item["category"],
                    emoji=item["emoji"],
                )
                supabase_upsert_gun(await self.bot.db.get_gun_any(guild_id, item["name"]))
                added.append(item["name"])
            elif (
                row["price"] != item["price"]
                or row["category"] != item["category"]
                or row["emoji"] != item["emoji"]
            ):
                await self.bot.db.edit_gun(
                    guild_id,
                    row["name"],
                    price=item["price"],
                    category=item["category"],
                    emoji=item["emoji"],
                )
                supabase_upsert_gun(await self.bot.db.get_gun_any(guild_id, row["name"]))
                updated.append(item["name"])

        for name_lower, row in existing.items():
            if name_lower not in target_names:
                await self.bot.db.remove_gun(guild_id, row["name"])
                supabase_upsert_gun(await self.bot.db.get_gun_any(guild_id, row["name"]))
                removed.append(row["name"])

        lines = []
        if added:
            lines.append(f"**Added:** {', '.join(added)}")
        if updated:
            lines.append(f"**Updated:** {', '.join(updated)}")
        if removed:
            lines.append(f"**Removed:** {', '.join(removed)} (deactivated, not deleted — history is kept)")
        if not lines:
            lines.append("Already up to date.")
        await interaction.response.send_message(f"{Emoji.GUN} Catalog synced.\n" + "\n".join(lines))

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
        supabase_upsert_gun(await self.bot.db.get_gun_any(str(interaction.guild_id), name))
        await interaction.response.send_message(f"🗑️ Removed **{name}** from the catalog.")

    @add.error
    @edit.error
    @remove.error
    @sync_defaults.error
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
