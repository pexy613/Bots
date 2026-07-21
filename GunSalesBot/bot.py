import logging

import discord
from discord.ext import commands

from .config import DEV_GUILD_ID, DISCORD_TOKEN
from .database import Database
from .seed_data import seed_guild

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gunsales")

INITIAL_COGS = [
    "GunSalesBot.cogs.settings",
    "GunSalesBot.cogs.catalog",
    "GunSalesBot.cogs.sales",
    "GunSalesBot.cogs.leaderboard",
    "GunSalesBot.cogs.dashboard",
    "GunSalesBot.cogs.goals",
    "GunSalesBot.cogs.profile",
]


class GunSalesBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.db = Database()

    async def setup_hook(self):
        await self.db.connect()
        for cog in INITIAL_COGS:
            await self.load_extension(cog)
            log.info("Loaded %s", cog)

        await self.tree.sync()
        log.info("Synced global commands (visible in every server, may take up to an hour to appear)")

        if DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Also synced commands instantly to dev guild %s", DEV_GUILD_ID)

    async def close(self):
        await self.db.close()
        await super().close()


bot = GunSalesBot()


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    for guild in bot.guilds:
        await seed_guild(bot.db, str(guild.id))


@bot.event
async def on_guild_join(guild: discord.Guild):
    await seed_guild(bot.db, str(guild.id))


def main():
    if not DISCORD_TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your bot token."
        )
    bot.run(DISCORD_TOKEN)


async def async_main():
    """Async version for concurrent bot launching."""
    if not DISCORD_TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your bot token."
        )
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(async_main())
