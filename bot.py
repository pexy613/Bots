import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()


def _read_token() -> str:
    for key in ("TOKEN", "DISCORD_TOKEN", "BOT_TOKEN"):
        value = (os.getenv(key) or "").strip().strip('"').strip("'")
        if value:
            return value
    return ""


TOKEN = _read_token()
COMBINED_PANELS_GUILD_ID = (os.getenv("COMBINED_PANELS_GUILD_ID") or os.getenv("DEV_GUILD_ID") or "").strip()


def _get_sync_guild():
    if not COMBINED_PANELS_GUILD_ID:
        return None
    try:
        return discord.Object(id=int(COMBINED_PANELS_GUILD_ID))
    except ValueError:
        return None


SYNC_GUILD = _get_sync_guild()

if not TOKEN:
    raise RuntimeError("No Discord bot token found. Add TOKEN=... or DISCORD_TOKEN=... to your .env file")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    try:
        # Cleanup old guild-scoped command copies that can appear as duplicates
        # after moving commands to global sync.
        if SYNC_GUILD:
            bot.tree.clear_commands(guild=SYNC_GUILD)
            await bot.tree.sync(guild=SYNC_GUILD)

        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s) globally.")
        print("Slash commands registered:", ", ".join(sorted(command.name for command in synced)))
    except Exception as exc:
        print(f"⚠️ Slash command sync failed: {exc}")


async def main():
    database.init_db()

    async with bot:
        await bot.load_extension("cogs.live_dashboard")
        await bot.load_extension("cogs.wash")
        await bot.load_extension("cogs.stats")
        await bot.load_extension("cogs.leaderboard")
        await bot.load_extension("cogs.dashboard")
        await bot.load_extension("cogs.receipts")
        await bot.load_extension("cogs.staff")
        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.panel")
        await bot.load_extension("cogs.goals")
        await bot.load_extension("cogs.combined_panels")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
