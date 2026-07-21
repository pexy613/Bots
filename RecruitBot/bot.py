import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("RECRUITBOT_TOKEN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("recruitbot")


class RecruitBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        log.info("Synced RecruitBot application commands")


bot = RecruitBot()


@bot.tree.command(name="recruit_ping", description="Check if RecruitBot is online")
async def recruit_ping(interaction: discord.Interaction):
    await interaction.response.send_message("RecruitBot is online.", ephemeral=True)


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)


def main():
    if not TOKEN:
        raise SystemExit("RECRUITBOT_TOKEN is not set. Add it to your .env to enable RecruitBot.")
    bot.run(TOKEN)


async def async_main():
    if not TOKEN:
        raise SystemExit("RECRUITBOT_TOKEN is not set. Add it to your .env to enable RecruitBot.")
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(async_main())
