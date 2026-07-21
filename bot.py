import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()
TOKEN = os.getenv("TOKEN")
COMBINED_PANELS_GUILD_ID = os.getenv("COMBINED_PANELS_GUILD_ID")

if not TOKEN:
    raise RuntimeError("TOKEN is missing. Create a .env file and add TOKEN=your_bot_token_here")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    synced = await bot.tree.sync()
    print(f"✅ Synced {len(synced)} slash command(s).")


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
        if COMBINED_PANELS_GUILD_ID:
            await bot.load_extension("cogs.combined_panels")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
