# GangBot Multi-Bot Setup

This workspace contains three Discord bots running from a unified launcher:
- **GangBot** - Money washing and management bot
- **GunSalesBot** - Gun sales tracking bot  
- **RecruitBot** - Recruitment bot (Pebblehost only for now)

## Setup Instructions

### 1. Install Git
Download and install from: https://git-scm.com/download/win

### 2. Create GitHub Repository
1. Go to https://github.com/new
2. Create a new repo (e.g., `discord-bots`)
3. Do NOT initialize with README/license/gitignore (we have our own)

### 3. Initialize Git Locally
After installing Git, run these commands in VS Code terminal:

```bash
cd c:\Users\adamf\OneDrive\Desktop\GangBot_v2_real
git init
git add .
git commit -m "Initial commit: unified bot setup"
git branch -M main
git remote add origin https://github.com/pexy613/Bots.git
git push -u origin main
```

### 4. Configure Pebblehost for Auto-Sync

On your Pebblehost server:

1. **SSH into the container** via Pebblehost's SFTP/Console
2. **Clone the repo** in the container root:
```bash
cd /home/container
git clone https://github.com/pexy613/Bots.git bot-repo
cp -r bot-repo/* ./
rm -rf bot-repo
```

3. **Update Bot Settings** in Pebblehost:
   - **Bot Language**: Python
   - **Bot Start File**: `launcher.py`
   - **Python Version**: 3.13+

4. **Add Auto-Pull Script** (optional but recommended):
   Create a startup script that pulls latest changes before starting bots.

### 5. Environment Variables

Copy `.env.template` to `.env` and fill in your bot tokens:

```env
TOKEN=your-gangbot-token
LEADERBOARD_CHANNEL_ID=your-channel-id
DISCORD_TOKEN=your-gunsalesbot-token
DEV_GUILD_ID=optional-dev-guild-id
RECRUITBOT_TOKEN=your-recruitbot-token
```

### Deploying Updates

From now on, to deploy changes:

```bash
# In VS Code terminal
git add .
git commit -m "Your changes here"
git push
```

Then on Pebblehost:
1. Go to Console
2. Run: `git pull && restart`

Or set up a webhook for automatic deployments (ask if you need help).

## Directory Structure

```
GangBot_v2_real/
├── launcher.py           # Main entry point (starts all bots)
├── requirements.txt      # Unified dependencies
├── .env                  # Your tokens (DON'T commit this!)
├── .env.template         # Template for .env
├── .gitignore            # Git ignore rules
│
├── GangBot_v2_real/      # GangBot source
│   ├── bot.py
│   ├── database.py
│   ├── cogs/
│   └── ...
│
├── GunSalesBot/          # GunSalesBot source
│   ├── bot.py
│   ├── config.py
│   ├── database.py
│   ├── cogs/
│   └── ...
│
└── RecruitBot/           # RecruitBot (synced from Pebblehost)
    └── ...
```

## Troubleshooting

**If a bot fails to start:**
- Check the logs in Pebblehost Console
- Verify the bot token is correct in `.env`
- Ensure all cogs are loading (check the cogs folder exists)

**If sync isn't working:**
- Verify you've run `git push` from VS Code
- Check Pebblehost file manager to see if files updated
- Sometimes Pebblehost caches - try a full server restart

## Local Testing

To test the launcher locally:

```bash
python launcher.py
```

Each bot will start and report status in the console.
