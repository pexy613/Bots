import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID") or None

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "gunsales.db")

DEFAULT_COMMISSION_PERCENT = 20.0
DEFAULT_DISCOUNT_PERCENT = 25.0


class Colors:
    SALE = 0x2ECC71
    LEADERBOARD = 0xF1C40F
    DASHBOARD = 0x3498DB
    GOAL = 0x9B59B6
    PROFILE = 0x1ABC9C
    CATALOG = 0xE67E22
    ERROR = 0xE74C3C


class Emoji:
    MONEY = "💵"
    PROFIT = "💰"
    SALES = "🧾"
    TROPHY = "🏆"
    MEDAL_1 = "🥇"
    MEDAL_2 = "🥈"
    MEDAL_3 = "🥉"
    TARGET = "🎯"
    CHART = "📊"
    CROWN = "👑"
    GUN = "🔫"
    CATEGORY = "🗂️"
    CALENDAR = "🗓️"
    CLOCK = "🕒"
    FIRE = "🔥"
    ID = "🆔"
