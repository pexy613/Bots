# Gun Sales Bot

A Discord bot for tracking weapon sales on a roleplay server: price catalog, sale receipts,
leaderboards, a live dashboard, dealer profiles, and server-wide sales goals.

## Setup

1. **Create the bot application**
   - Go to https://discord.com/developers/applications → New Application.
   - Under **Bot**, click **Reset Token** and copy it (you'll need it below).
   - Under **Bot**, enable no privileged intents — this bot doesn't need Message Content, Presence, or Members intents.
   - Under **OAuth2 → URL Generator**, check scopes `bot` and `applications.commands`, and under
     Bot Permissions check `Send Messages`, `Embed Links`, `Use Slash Commands`. Use the generated
     URL to invite the bot to your server.

2. **Install dependencies** (Python 3.11+ recommended)
   ```powershell
   cd C:\Users\adamf\GunSalesBot
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Configure the token**
   - Copy `.env.example` to `.env`.
   - Paste your bot token into `DISCORD_TOKEN`.
   - Optional: set `DEV_GUILD_ID` to your server's ID while testing — this makes slash commands
     sync instantly instead of waiting up to an hour for the global sync.

4. **Run it**
   ```powershell
   python bot.py
   ```

The weapon catalog you gave me (AP Pistol, Desert Eagle, FN Pistol, G3, M1911, Mossberg Shotgun,
QBZ 95, Sniper, Stun Gun, TAR 21) is seeded automatically into any server the bot joins.

## Commands

**Sales**
- `/sale panel` *(admin, run once per channel)* — posts a persistent **Log Sale** button. Anyone
  can click it to log a sale through a dropdown builder (weapon, price — including a custom
  price option) instead of typing a command; quantity is the only typed field, and it's required
  before the log button unlocks. The panel reposts itself at the bottom of the channel after
  every log, so it's always there ready for the next one.
- Every receipt has a small ✖️ button — the seller who logged it (or an admin) can use it to
  delete a mis-entered sale on the spot.
- `/sale history` — recent sales, optionally filtered by seller.
- `/sale edit` *(admin)* — correct a sale's quantity or price.
- `/sale delete` *(admin)* — remove a logged sale.

**Catalog**
- `/catalog view` — the full price list, grouped by category.
- `/catalog add` / `/catalog edit` / `/catalog remove` *(admin)* — manage weapons and prices.

**Stats**
- `/leaderboard panel` *(admin, run once per channel)* — posts a live leaderboard (lifetime,
  amount washed) that automatically updates every time a sale is logged or deleted.
- `/leaderboard show` — a one-time snapshot, filterable by timeframe (today/7d/30d/lifetime) and
  metric (amount washed, profit, sale count).
- `/dashboard panel` *(admin, run once per channel)* — posts a live dashboard (today / 7-day /
  30-day / lifetime totals plus top dealer) that automatically updates after every sale.
- `/dashboard show` — a one-time dashboard snapshot.
- `/profile [member]` — a dealer's rank, today/30-day/lifetime stats.

**Goals**
- `/goal set` *(admin)* — start a weapon sales dollar target (with an optional deadline) and post a
  live panel that automatically updates its progress bar after every sale.
- `/goal progress` — a one-time snapshot of progress toward the active goal.
- `/goal end` *(admin)* — close out the active goal (the live panel updates to show it ended).
- `/goal list` — recent goals and their status.

**Config**
- `/config commission` *(admin)* — set the % commission sellers earn on each sale (default 20%).
- `/config logchannel` *(admin)* — mirror every sale receipt into a specific channel.
- `/config show` — view current settings.

Admin commands require the **Manage Server** permission.

## Data

Everything is stored locally in `data/gunsales.db` (SQLite) — no external services required.
Back that file up if you care about sales history; deleting it wipes all sales, goals, and any
catalog edits (the default catalog will simply be reseeded on next startup).

## Notes on the numbers

- **Ally price** = full price minus each weapon's discount % (25% by default, editable per weapon
  via `/catalog edit`).
- **Profit** on a sale = total sale amount × the server's commission % (`/config commission`),
  mirroring how the reference "washed / commission / profit" receipt worked, but applied to gun sales.
