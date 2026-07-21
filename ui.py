import time
import discord

BOT_NAME = "The Ledger"
FOOTER = "The Ledger • Internal Management System"

PRIMARY = discord.Color.from_rgb(255, 215, 0)
SUCCESS = discord.Color.from_rgb(0, 196, 111)
ERROR = discord.Color.from_rgb(255, 90, 90)
DASHBOARD = discord.Color.from_rgb(88, 101, 242)
LEADERBOARD = discord.Color.from_rgb(255, 153, 0)
ACCENT = discord.Color.from_rgb(124, 92, 255)

THUMBNAIL = None
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━"


def create_embed(title, color=PRIMARY, description=None, footer=None):
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    if description:
        embed.description = description

    if THUMBNAIL:
        embed.set_thumbnail(url=THUMBNAIL)

    embed.set_footer(text=footer or FOOTER)
    return embed


def money(value):
    return f"${int(value):,}"


def dashboard_block(washed, profit, washes):
    return (
        f"**💵 Washed**\n{money(washed)}\n\n"
        f"**💰 Profit**\n{money(profit)}\n\n"
        f"**🧼 Washes**\n{washes}"
    )


def dashboard_embed(today, week, month, lifetime, top_user):
    embed = create_embed(
        "🏦 THE LEDGER",
        DASHBOARD,
        f"{DIVIDER}\n### Live financial overview\nReal-time laundering statistics and staff activity.\n{DIVIDER}"
    )

    embed.add_field(
        name="📊 TODAY",
        value=dashboard_block(today[1], today[2], today[0]),
        inline=True
    )

    if top_user:
        top_name = top_user[0]
        top_amount = money(top_user[1])
    else:
        top_name = "No data yet"
        top_amount = "$0"

    embed.add_field(
        name="👑 TOP WASHER",
        value=f"**{top_name}**\n\n💵 {top_amount}",
        inline=True
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(
        name="📅 LAST 7 DAYS",
        value=dashboard_block(week[1], week[2], week[0]),
        inline=True
    )

    embed.add_field(
        name="📆 LAST 30 DAYS",
        value=dashboard_block(month[1], month[2], month[0]),
        inline=True
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(
        name="📈 LIFETIME",
        value=dashboard_block(lifetime[1], lifetime[2], lifetime[0]),
        inline=False
    )

    embed.set_footer(text=f"{FOOTER} • Updated {time.strftime('%I:%M %p')}")
    return embed


def receipt_embed(wash_id, amount, percentage, profit, member):
    embed = create_embed(
        "🧾 TRANSACTION RECEIPT",
        SUCCESS,
        f"{DIVIDER}\n**Transaction #{wash_id}**\n{DIVIDER}"
    )

    embed.add_field(name="💵 Amount Washed", value=money(amount), inline=True)
    embed.add_field(name="📉 Commission", value=f"{percentage}%", inline=True)
    embed.add_field(name="💰 Profit", value=money(profit), inline=True)
    embed.add_field(name="👤 Logged By", value=member.mention, inline=False)

    return embed