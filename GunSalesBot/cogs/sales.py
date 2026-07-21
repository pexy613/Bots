from typing import Optional

import discord
from discord import SeparatorSpacing, app_commands
from discord.ext import commands
from discord.ui import ActionRow, Button, Container, LayoutView, Modal, Section, Select, Separator, TextDisplay, TextInput

from .dashboard import update_live_dashboard
from .goals import update_live_goal
from .leaderboard import update_live_leaderboard
from ..config import Colors, Emoji
from ..utils.layouts import DeleteSaleButton, error_view, notice_view, sale_history_view, sale_receipt_view
from ..utils.formatting import money

PANEL_BUTTON_CUSTOM_ID = "gunsales:log_sale_button"


async def _create_sale(
    bot: commands.Bot,
    interaction: discord.Interaction,
    *,
    record,
    quantity: int,
    unit_price: int,
    price_label: str,
) -> dict:
    credited = interaction.user
    guild_id = str(interaction.guild_id)
    settings = await bot.db.get_settings(guild_id)
    commission_percent = settings["commission_percent"]
    total_amount = unit_price * quantity
    profit = round(total_amount * commission_percent / 100)

    sale_id = await bot.db.add_sale(
        guild_id=guild_id,
        gun_name=record["name"],
        category=record["category"],
        quantity=quantity,
        unit_price=unit_price,
        price_type=price_label,
        total_amount=total_amount,
        commission_percent=commission_percent,
        profit=profit,
        seller_id=str(credited.id),
        seller_name=str(credited),
    )
    return {
        "sale_id": sale_id,
        "settings": settings,
        "commission_percent": commission_percent,
        "total_amount": total_amount,
        "profit": profit,
        "credited": credited,
    }


def _build_receipt(record, quantity, unit_price, price_label, sale: dict) -> LayoutView:
    return sale_receipt_view(
        sale_id=sale["sale_id"],
        gun_emoji=record["emoji"],
        gun_name=record["name"],
        quantity=quantity,
        unit_price=unit_price,
        price_type=price_label,
        total_amount=sale["total_amount"],
        commission_percent=sale["commission_percent"],
        profit=sale["profit"],
        seller=sale["credited"],
    )


async def _mirror_to_log_channel(bot: commands.Bot, interaction: discord.Interaction, settings, receipt_builder):
    if settings["log_channel_id"] and int(settings["log_channel_id"]) != interaction.channel_id:
        log_channel = interaction.guild.get_channel(int(settings["log_channel_id"]))
        if log_channel:
            await log_channel.send(view=receipt_builder())


async def _repost_panel(bot: commands.Bot, channel, old_panel_message_id: int) -> None:
    try:
        old_panel = await channel.fetch_message(old_panel_message_id)
        await old_panel.delete()
    except (discord.NotFound, discord.Forbidden):
        pass
    await channel.send(view=LogSalePanelView(bot))


# ---------- sale builder (opened by the panel button) ----------


class WeaponSelect(Select):
    def __init__(self, guns: list):
        options = [
            discord.SelectOption(
                label=g["name"],
                description=f"{money(g['price'])} full price",
                emoji=g["emoji"] or None,
                value=g["name"],
            )
            for g in guns[:25]
        ]
        super().__init__(placeholder="Weapon (required)", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: SaleBuilderView = self.view
        view.gun_name = self.values[0]
        for opt in self.options:
            opt.default = opt.value == view.gun_name
        await view.refresh(interaction)


class CustomPriceModal(Modal, title="Custom Price"):
    price = TextInput(label="Price per unit", placeholder="e.g. 25000")

    def __init__(self, builder_view: "SaleBuilderView", price_select: "PriceTypeSelect"):
        super().__init__()
        self.builder_view = builder_view
        self.price_select = price_select
        if builder_view.custom_price:
            self.price.default = str(builder_view.custom_price)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.price.value.strip().replace("$", "").replace(",", "")
        try:
            value = int(raw)
            if value < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                view=error_view("Price must be a whole number."), ephemeral=True
            )
            return
        self.builder_view.price_type = "custom"
        self.builder_view.custom_price = value
        for opt in self.price_select.options:
            opt.default = opt.value == "custom"
        await self.builder_view.refresh(interaction)


class PriceTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Full price", value="full", default=True),
            discord.SelectOption(label="Ally price (discounted)", value="ally"),
            discord.SelectOption(label="Custom price", value="custom"),
        ]
        super().__init__(placeholder="Price (default Full)", options=options, min_values=0, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: SaleBuilderView = self.view
        selected = self.values[0] if self.values else "full"
        if selected == "custom":
            await interaction.response.send_modal(CustomPriceModal(view, self))
            return
        view.price_type = selected
        view.custom_price = None
        for opt in self.options:
            opt.default = opt.value == selected
        await view.refresh(interaction)


class QuantityModal(Modal, title="Set Quantity"):
    quantity = TextInput(label="Quantity", placeholder="e.g. 3 (default 1)", max_length=5)

    def __init__(self, builder_view: "SaleBuilderView"):
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.quantity.value.strip()
        try:
            value = int(raw)
            if value < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                view=error_view("Quantity must be a whole number of 1 or more."), ephemeral=True
            )
            return
        self.builder_view.quantity = value
        self.builder_view.quantity_set = True
        await self.builder_view.refresh(interaction)


class QuantityButton(Button):
    def __init__(self):
        super().__init__(label="Set Quantity", style=discord.ButtonStyle.secondary, emoji="🔢")

    async def callback(self, interaction: discord.Interaction):
        view: SaleBuilderView = self.view
        await interaction.response.send_modal(QuantityModal(view))


class SubmitButton(Button):
    def __init__(self):
        super().__init__(label="Log Sale", style=discord.ButtonStyle.success, emoji="✅")

    async def callback(self, interaction: discord.Interaction):
        view: SaleBuilderView = self.view
        if view.gun_name is None:
            await interaction.response.send_message(view=error_view("Pick a weapon first."), ephemeral=True)
            return
        if not view.quantity_set:
            await interaction.response.send_message(
                view=error_view("Set a quantity first."), ephemeral=True
            )
            return
        if view.price_type == "custom" and view.custom_price is None:
            await interaction.response.send_message(
                view=error_view("Set a custom price first."), ephemeral=True
            )
            return

        # Acknowledge immediately — everything past this point does DB/Discord I/O and
        # could otherwise blow past Discord's 3-second interaction response window.
        await interaction.response.defer()

        record = next(g for g in view.guns if g["name"] == view.gun_name)
        if view.price_type == "ally":
            unit_price = round(record["price"] * (1 - record["discount_percent"] / 100))
        elif view.price_type == "custom":
            unit_price = view.custom_price
        else:
            unit_price = record["price"]

        sale = await _create_sale(
            view.bot,
            interaction,
            record=record,
            quantity=view.quantity,
            unit_price=unit_price,
            price_label=view.price_type,
        )

        await interaction.edit_original_response(
            view=notice_view(f"{Emoji.SALES} Logged sale `#{sale['sale_id']}` — receipt posted below.", Colors.SALE)
        )
        await interaction.followup.send(view=_build_receipt(record, view.quantity, unit_price, view.price_type, sale))
        await _mirror_to_log_channel(
            view.bot,
            interaction,
            sale["settings"],
            lambda: _build_receipt(record, view.quantity, unit_price, view.price_type, sale),
        )
        await _repost_panel(view.bot, interaction.channel, view.panel_message_id)
        if interaction.guild:
            await update_live_leaderboard(view.bot, interaction.guild)
            await update_live_dashboard(view.bot, interaction.guild)
            await update_live_goal(view.bot, interaction.guild)


class CancelButton(Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=notice_view("Cancelled — nothing was logged.", discord.Color.dark_grey().value)
        )


class SaleBuilderView(LayoutView):
    def __init__(self, bot: commands.Bot, guns: list, panel_message_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guns = guns
        self.panel_message_id = panel_message_id
        self.gun_name: Optional[str] = None
        self.quantity: int = 1
        self.quantity_set: bool = False
        self.price_type: str = "full"
        self.custom_price: Optional[int] = None

        container = Container(accent_colour=Colors.SALE)
        container.add_item(TextDisplay(f"# {Emoji.SALES} Log a Sale"))
        self.summary = TextDisplay(self._summary_text())
        container.add_item(self.summary)
        container.add_item(Separator(spacing=SeparatorSpacing.small))
        container.add_item(ActionRow(WeaponSelect(guns)))
        container.add_item(ActionRow(PriceTypeSelect()))
        self.submit_button = SubmitButton()
        self.submit_button.disabled = True
        container.add_item(ActionRow(QuantityButton(), self.submit_button, CancelButton()))
        self.add_item(container)

    def _summary_text(self) -> str:
        gun = f"**{self.gun_name}**" if self.gun_name else "*no weapon picked yet*"
        quantity = f"×{self.quantity}" if self.quantity_set else "*quantity not set*"
        if self.price_type == "ally":
            price = "Ally price"
        elif self.price_type == "custom":
            price = f"Custom {money(self.custom_price)}" if self.custom_price else "*custom price not set*"
        else:
            price = "Full price"
        return f"{gun} {quantity} · {price}"

    async def refresh(self, interaction: discord.Interaction):
        self.summary.content = self._summary_text()
        price_ready = self.price_type != "custom" or self.custom_price is not None
        self.submit_button.disabled = not (self.gun_name and self.quantity_set and price_ready)
        await interaction.response.edit_message(view=self)


class LogSaleButton(Button):
    def __init__(self, bot: commands.Bot):
        super().__init__(
            label="Log Sale",
            style=discord.ButtonStyle.success,
            emoji="📝",
            custom_id=PANEL_BUTTON_CUSTOM_ID,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        guns = await self.bot.db.list_guns(str(interaction.guild_id))
        if not guns:
            await interaction.response.send_message(
                view=error_view("No weapons in the catalog yet. Ask an admin to run `/catalog add`."),
                ephemeral=True,
            )
            return
        view = SaleBuilderView(self.bot, guns, panel_message_id=interaction.message.id)
        await interaction.response.send_message(view=view, ephemeral=True)


class LogSalePanelView(LayoutView):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        container = Container(accent_colour=Colors.SALE)
        container.add_item(
            Section(
                TextDisplay(f"# {Emoji.SALES} Log a Sale"),
                TextDisplay("Press the button and pick what you sold — quantity's the only thing you'll type."),
                accessory=LogSaleButton(bot),
            )
        )
        self.add_item(container)


class Sales(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(LogSalePanelView(self.bot))
        self.bot.add_dynamic_items(DeleteSaleButton)

    sale_group = app_commands.Group(name="sale", description="Log and manage weapon sales")

    @sale_group.command(name="panel", description="[Admin] Post a persistent Log Sale button in this channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=LogSalePanelView(self.bot))

    @sale_group.command(name="history", description="Show recent logged sales")
    @app_commands.describe(seller="Only show sales from this seller", limit="How many to show (max 25)")
    async def history(
        self,
        interaction: discord.Interaction,
        seller: Optional[discord.Member] = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        rows = await self.bot.db.list_sales(
            str(interaction.guild_id),
            seller_id=str(seller.id) if seller else None,
            limit=limit,
        )
        if not rows:
            await interaction.response.send_message(
                view=error_view("No sales logged yet."), ephemeral=True
            )
            return

        await interaction.response.send_message(view=sale_history_view(rows))

    @sale_group.command(name="edit", description="[Admin] Edit a logged sale")
    @app_commands.describe(
        sale_id="ID of the sale (shown on its receipt)",
        quantity="New quantity",
        unit_price="New unit price",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit(
        self,
        interaction: discord.Interaction,
        sale_id: int,
        quantity: app_commands.Range[int, 1] = None,
        unit_price: app_commands.Range[int, 1] = None,
    ):
        sale = await self.bot.db.get_sale(sale_id)
        if not sale or sale["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message(view=error_view("Sale not found."), ephemeral=True)
            return

        new_quantity = quantity if quantity is not None else sale["quantity"]
        new_unit_price = unit_price if unit_price is not None else sale["unit_price"]
        new_total = new_quantity * new_unit_price
        new_profit = round(new_total * sale["commission_percent"] / 100)

        await self.bot.db.update_sale(
            sale_id,
            quantity=new_quantity,
            unit_price=new_unit_price,
            total_amount=new_total,
            profit=new_profit,
        )
        await interaction.response.send_message(
            f"✏️ Updated sale `#{sale_id}` — now {money(new_total)} ({new_quantity}x @ {money(new_unit_price)})."
        )
        if interaction.guild:
            await update_live_leaderboard(self.bot, interaction.guild)
            await update_live_dashboard(self.bot, interaction.guild)
            await update_live_goal(self.bot, interaction.guild)

    @sale_group.command(name="delete", description="[Admin] Delete a logged sale")
    @app_commands.describe(sale_id="ID of the sale to delete")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete(self, interaction: discord.Interaction, sale_id: int):
        sale = await self.bot.db.get_sale(sale_id)
        if not sale or sale["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message(view=error_view("Sale not found."), ephemeral=True)
            return
        await self.bot.db.delete_sale(sale_id)
        await interaction.response.send_message(f"🗑️ Deleted sale `#{sale_id}`.")
        if interaction.guild:
            await update_live_leaderboard(self.bot, interaction.guild)
            await update_live_dashboard(self.bot, interaction.guild)
            await update_live_goal(self.bot, interaction.guild)

    @panel.error
    @edit.error
    @delete.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                view=error_view("You need the **Manage Server** permission to do that."),
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Sales(bot))
