GangBot v2 setup
================

1. Extract this folder somewhere easy, for example Desktop/GangBot_v2_real.
2. Copy your old .env file into this new folder, or rename .env.example to .env and paste your token:

   TOKEN=your_bot_token_here

3. Invite the bot to as many servers as you want. It's multi-server aware: each
   server manages its own wash log, channels, and data automatically.

   In each server, make sure you have:
   - A text channel with "wash-log" in its name (for /wash).
   - A text channel with "announcements" in its name (for /today, /week, /month, /lifetime, /staff).
   - A text channel with "leaderboard" in its name (for /leaderboard, /setupleaderboard).
   - A text channel with "live-dashboard" in its name (for /dashboard, /setupdashboard).
   - A role with "management" in its name for anyone who should be able to use management commands.

   No config file editing or setup commands needed — the bot finds these by name in each server.
   The bot also needs "View Channel" permission on each of these (especially if they're private
   channels), or it won't be able to detect them.

4. Open terminal inside this folder and run:

   py -m pip install -r requirements.txt
   py bot.py

5. In Discord:
   - Use /wash in the wash log channel.
   - Use /today, /week, /month, /lifetime, /staff in the announcements channel.
   - Use /setupleaderboard once in the leaderboard channel to make it auto-update after every wash.
   - Use /setupdashboard once in the live dashboard channel to make it auto-update after every wash.

Main commands
=============
/wash - Opens a popup to log a wash.
/today - Today's totals.
/week - Last 7 days.
/month - Last 30 days.
/lifetime - Lifetime totals.
/leaderboard - Top washers (one-time snapshot).
/setupleaderboard - Creates the permanent live leaderboard (auto-updates after every wash).
/resetleaderboard - Resets the saved live leaderboard message.
/dashboard - One-time dashboard post.
/setupdashboard - Creates the permanent live dashboard (auto-updates after every wash).
/resetdashboard - Resets the saved live dashboard message.
/refreshdashboard - Force-refreshes the live dashboard and leaderboard.
/receipt - View a wash by ID.
/deletewash - Deletes a single wash log by ID and refreshes the dashboard, leaderboard, and goal progress.
/resetwashes - Deletes ALL wash logs for this server and resets totals.
/staff - View a member's stats.
/export - Export this server's washes to CSV.
/backup - Backup the whole database file (bot owner only, contains every server's data).
/setgoal, /setupgoal, /showgoal - Weekly goal tracking.
/setuplogpanel - Creates the Log Wash button panel.

Notes
=====
- The bot creates laundering.db automatically, and each server's data is kept separate.
- Every wash updates that server's live dashboard and live leaderboard automatically.
- There is no more 80/20 profit split — a wash log just shows the amount washed and the
  commission percentage/profit earned. There is no "panel deposit" concept anymore.
- If slash commands do not show immediately (especially brand new ones like /deletewash,
  /setupleaderboard, /resetleaderboard), restart the bot once and give Discord up to an hour
  to propagate new global commands to a server for the first time.
