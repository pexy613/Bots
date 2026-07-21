from datetime import datetime, timezone
from typing import Optional

import discord
from discord import SeparatorSpacing
from discord.ui import ActionRow, Button, Container, DynamicItem, LayoutView, Section, Separator, TextDisplay, Thumbnail

from config import Colors, Emoji
from utils.formatting import discord_timestamp, money, percent, progress_bar, rank_medal

BRAND = "Black Market Firearms · Sales Ledger"


class DeleteSaleButton(
    DynamicItem[Button], template=r"gunsales:delete_sale:(?P<sale_id>[0-9]+):(?P<seller_id>[0-9]+)"
):
    """A small 'X' on every receipt. Lets the seller who logged it (or an admin) undo a typo."""

    def __init__(self, sale_id: int, seller_id: int):
        super().__init__(
            Button(
                style=discord.ButtonStyle.danger,
                emoji="✖️",
                custom_id=f"gunsales:delete_sale:{sale_id}:{seller_id}",
            )
        )
        self.sale_id = sale_id
        self.seller_id = seller_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["sale_id"]), int(match["seller_id"]))

    async def callback(self, interaction: discord.Interaction):
        is_owner = interaction.user.id == self.seller_id
        is_admin = interaction.user.guild_permissions.manage_guild
        if not (is_owner or is_admin):
            await interaction.response.send_message(
                view=error_view("Only the seller who logged this (or an admin) can delete it."),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        deleted = await interaction.client.db.delete_sale(self.sale_id)
        if not deleted:
            await interaction.followup.send(
                view=error_view("This sale was already deleted."), ephemeral=True
            )
            return

        await interaction.edit_original_response(
            view=notice_view(f"🗑️ Sale `#{self.sale_id}` deleted by {interaction.user.mention}.", Colors.ERROR)
        )

        if interaction.guild:
            from cogs.dashboard import update_live_dashboard
            from cogs.goals import update_live_goal
            from cogs.leaderboard import update_live_leaderboard

            await update_live_leaderboard(interaction.client, interaction.guild)
            await update_live_dashboard(interaction.client, interaction.guild)
            await update_live_goal(interaction.client, interaction.guild)


def _view(container: Container) -> LayoutView:
    view = LayoutView(timeout=None)
    view.add_item(container)
    return view


def _footer() -> TextDisplay:
    return TextDisplay(f"-# {BRAND} · {discord_timestamp(datetime.now(timezone.utc), 'f')}")


def sale_receipt_view(
    sale_id: int,
    gun_emoji: str,
    gun_name: str,
    quantity: int,
    unit_price: int,
    price_type: str,
    total_amount: int,
    commission_percent: float,
    profit: int,
    seller: discord.abc.User,
) -> LayoutView:
    container = Container(accent_colour=Colors.SALE)
    container.add_item(
        Section(
            TextDisplay(f"# {Emoji.SALES} Weapon Sale Receipt"),
            TextDisplay(f"Sale `#{sale_id}`"),
            accessory=Thumbnail(seller.display_avatar.url),
        )
    )
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(
        TextDisplay(
            f"### {gun_emoji} {gun_name}\n"
            f"×{quantity} @ {money(unit_price)} · _{price_type} price_"
        )
    )
    container.add_item(
        TextDisplay(
            f"{Emoji.MONEY} **{money(total_amount)}** total "
            f"{Emoji.PROFIT} **{money(profit)}** commission ({percent(commission_percent)})"
        )
    )
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(TextDisplay(f"**Seller** {seller.mention}"))
    container.add_item(ActionRow(DeleteSaleButton(sale_id, seller.id)))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def catalog_view(guild_name: str, guns: list) -> LayoutView:
    container = Container(accent_colour=Colors.CATALOG)
    container.add_item(TextDisplay(f"# {Emoji.GUN} Weapon Catalog"))
    container.add_item(TextDisplay(f"Current price list for **{guild_name}**"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))

    by_category: dict[str, list] = {}
    for gun in guns:
        by_category.setdefault(gun["category"] or "Uncategorized", []).append(gun)

    first = True
    for category, items in by_category.items():
        if not first:
            container.add_item(Separator(spacing=SeparatorSpacing.small, visible=False))
        first = False
        lines = [f"### {Emoji.CATEGORY} {category}"]
        for gun in items:
            ally_price = round(gun["price"] * (1 - gun["discount_percent"] / 100))
            lines.append(
                f"{gun['emoji']} **{gun['name']}** — {money(gun['price'])}\n"
                f"　Ally min ({percent(gun['discount_percent'])} off): {money(ally_price)}"
            )
        container.add_item(TextDisplay("\n".join(lines)))

    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def leaderboard_view(timeframe_label: str, metric_label: str, rows: list) -> LayoutView:
    container = Container(accent_colour=Colors.LEADERBOARD)
    container.add_item(TextDisplay(f"# {Emoji.TROPHY} Top Dealers"))
    container.add_item(TextDisplay(f"Ranked by **{metric_label}** · {timeframe_label}"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))

    if not rows:
        container.add_item(TextDisplay("*No sales yet — be the first to log one!*"))
    else:
        for i, row in enumerate(rows, start=1):
            container.add_item(
                TextDisplay(
                    f"### {rank_medal(i)} {row['seller_name']}\n"
                    f"{Emoji.MONEY} Washed **{money(row['washed'])}** "
                    f"{Emoji.PROFIT} Profit **{money(row['profit'])}** "
                    f"{Emoji.SALES} Sales **{row['count']}**"
                )
            )

    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def dashboard_view(
    guild_name: str,
    today: dict,
    last7: dict,
    last30: dict,
    lifetime: dict,
    top_seller: Optional[dict],
) -> LayoutView:
    def block(label: str, stats: dict) -> str:
        return (
            f"**{label}**\n"
            f"{Emoji.MONEY} Washed **{money(stats['washed'])}** "
            f"{Emoji.PROFIT} Profit **{money(stats['profit'])}** "
            f"{Emoji.SALES} Sales **{stats['count']}**"
        )

    container = Container(accent_colour=Colors.DASHBOARD)
    container.add_item(TextDisplay(f"# {Emoji.CHART} The Ledger"))
    container.add_item(TextDisplay(f"Real-time sales dashboard for **{guild_name}**"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))

    if top_seller:
        top_text = f"**{top_seller['seller_name']}** · {money(top_seller['washed'])} washed"
    else:
        top_text = "*No sales yet*"
    container.add_item(TextDisplay(f"{Emoji.CROWN} **Top Dealer**\n{top_text}"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))

    container.add_item(TextDisplay(block(f"{Emoji.CLOCK} Today", today)))
    container.add_item(TextDisplay(block(f"{Emoji.CALENDAR} Last 7 Days", last7)))
    container.add_item(TextDisplay(block(f"{Emoji.CALENDAR} Last 30 Days", last30)))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(TextDisplay(block(f"{Emoji.FIRE} Lifetime", lifetime)))

    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def goal_view(goal, current_amount: float) -> LayoutView:
    target_display = money(goal["target_amount"])
    current_display = money(current_amount)
    status = "🟢 Active" if goal["active"] else "🔴 Ended"

    container = Container(accent_colour=Colors.GOAL)
    container.add_item(TextDisplay(f"# {Emoji.TARGET} Weapon Sales Goal"))
    container.add_item(TextDisplay(status))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(TextDisplay(progress_bar(current_amount, goal["target_amount"])))
    container.add_item(
        TextDisplay(f"Sold so far: **{current_display}**   Target: **{target_display}**")
    )
    if goal["end_at"]:
        from utils.formatting import parse_iso

        container.add_item(TextDisplay(f"Deadline: {discord_timestamp(parse_iso(goal['end_at']), 'R')}"))

    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def profile_view(
    member: discord.abc.User,
    rank: Optional[int],
    today: dict,
    last30: dict,
    lifetime: dict,
) -> LayoutView:
    def block(label: str, stats: dict) -> str:
        return f"**{label}**\n{money(stats['washed'])} washed · {money(stats['profit'])} profit"

    rank_text = rank_medal(rank) if rank else "*Unranked*"

    container = Container(accent_colour=Colors.PROFILE)
    container.add_item(
        Section(
            TextDisplay(f"# {Emoji.ID} Dealer Profile"),
            TextDisplay(f"**{member.display_name}**"),
            TextDisplay(f"Rank {rank_text} · {lifetime['count']} lifetime sales"),
            accessory=Thumbnail(member.display_avatar.url),
        )
    )
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(TextDisplay(block(f"{Emoji.CLOCK} Today", today)))
    container.add_item(TextDisplay(block(f"{Emoji.CALENDAR} Last 30 Days", last30)))
    container.add_item(TextDisplay(block(f"{Emoji.FIRE} Lifetime", lifetime)))

    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def sale_history_view(rows: list) -> LayoutView:
    from utils.formatting import truncate

    container = Container(accent_colour=Colors.SALE)
    container.add_item(TextDisplay(f"# {Emoji.SALES} Recent Sales"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(
        TextDisplay(
            "\n".join(
                f"`#{r['id']}` **{r['gun_name']}** ×{r['quantity']} — {money(r['total_amount'])} "
                f"· {r['seller_name']} · {truncate(r['created_at'], 19)}"
                for r in rows
            )
        )
    )
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def goal_list_view(goals: list) -> LayoutView:
    container = Container(accent_colour=Colors.GOAL)
    container.add_item(TextDisplay(f"# {Emoji.TARGET} Weapon Sales Goals"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    lines = []
    for g in goals:
        status = "🟢" if g["active"] else "⚪"
        lines.append(f"{status} `#{g['id']}` Target **{money(g['target_amount'])}**")
    container.add_item(TextDisplay("\n".join(lines)))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def settings_view(commission_percent: float, channel_text: str) -> LayoutView:
    container = Container(accent_colour=discord.Color.dark_grey().value)
    container.add_item(TextDisplay("# ⚙️ Bot Configuration"))
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(
        TextDisplay(f"**Commission**\n{commission_percent}%\n\n**Log Channel**\n{channel_text}")
    )
    container.add_item(Separator(spacing=SeparatorSpacing.small))
    container.add_item(_footer())
    return _view(container)


def error_view(message: str) -> LayoutView:
    container = Container(accent_colour=Colors.ERROR)
    container.add_item(TextDisplay(f"### ⚠️ Error\n{message}"))
    return _view(container)


def notice_view(text: str, color: int = Colors.SALE) -> LayoutView:
    container = Container(accent_colour=color)
    container.add_item(TextDisplay(text))
    return _view(container)
