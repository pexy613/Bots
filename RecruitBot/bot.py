import asyncio
import logging
import os
import sqlite3
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("RECRUITBOT_TOKEN")
DB_PATH = os.path.join(os.path.dirname(__file__), "recruits.db")

REQUEST_EXPIRY_SECONDS = 24 * 60 * 60
RESUBMIT_SECONDS = 10 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("recruitbot")


def setup_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            request_channel_id INTEGER,
            approval_channel_id INTEGER,
            staff_role_id INTEGER,
            unverified_role_id INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rank_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            UNIQUE(guild_id, name)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recruits (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            player_name TEXT,
            player_id TEXT,
            rank_name TEXT,
            rank_role_id INTEGER,
            nickname TEXT,
            approved INTEGER DEFAULT 0,
            submitted_at INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """
    )

    conn.commit()
    conn.close()


def backup_db_candidates() -> list[str]:
    base_dir = os.path.dirname(__file__)
    repo_root = os.path.dirname(base_dir)
    return [
        os.path.join(base_dir, "recruits_backup.db"),
        os.path.join(base_dir, "recruits.old.db"),
        os.path.join(repo_root, "recovered_exports", "latest", "RecruitBot", "recruits.db"),
        os.path.join(repo_root, "recovered_exports", "RecruitBot", "recruits.db"),
    ]


def resolve_backup_db_path(source_path: str | None) -> str | None:
    if source_path:
        candidate = source_path.strip()
        if os.path.isabs(candidate):
            return candidate if os.path.exists(candidate) else None

        base_dir = os.path.dirname(__file__)
        repo_root = os.path.dirname(base_dir)
        relative_paths = [
            os.path.join(base_dir, candidate),
            os.path.join(repo_root, candidate),
        ]
        for path in relative_paths:
            if os.path.exists(path):
                return path
        return None

    for path in backup_db_candidates():
        if os.path.exists(path):
            return path
    return None


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_guild_config(guild_id: int) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT request_channel_id, approval_channel_id, staff_role_id, unverified_role_id FROM guild_config WHERE guild_id = ?",
        (guild_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "request_channel_id": None,
            "approval_channel_id": None,
            "staff_role_id": None,
            "unverified_role_id": None,
        }

    return {
        "request_channel_id": row[0],
        "approval_channel_id": row[1],
        "staff_role_id": row[2],
        "unverified_role_id": row[3],
    }


def set_guild_config(guild_id: int, **fields) -> None:
    config = get_guild_config(guild_id)
    config.update(fields)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO guild_config
        (guild_id, request_channel_id, approval_channel_id, staff_role_id, unverified_role_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            config["request_channel_id"],
            config["approval_channel_id"],
            config["staff_role_id"],
            config["unverified_role_id"],
        ),
    )
    conn.commit()
    conn.close()


def get_rank_options(guild_id: int) -> list[tuple[str, int]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, role_id FROM rank_options WHERE guild_id = ? ORDER BY name ASC",
        (guild_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_rank_option(guild_id: int, name: str, role_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO rank_options (guild_id, name, role_id) VALUES (?, ?, ?)",
        (guild_id, name, role_id),
    )
    conn.commit()
    conn.close()


def remove_rank_option(guild_id: int, name: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM rank_options WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, name),
    )
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def import_backup_for_guild(
    *,
    source_db_path: str,
    target_guild_id: int,
    source_guild_id: int | None = None,
) -> tuple[int, bool, int]:
    """Import setup config and rank options from a backup recruits.db."""
    src = sqlite3.connect(source_db_path)
    src.row_factory = sqlite3.Row
    cur = src.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    if "guild_config" not in tables and "rank_options" not in tables:
        src.close()
        raise ValueError("Backup database does not contain expected RecruitBot tables.")

    resolved_source_guild_id = source_guild_id
    if resolved_source_guild_id is None:
        cur.execute("SELECT guild_id FROM guild_config LIMIT 1")
        row = cur.fetchone()
        if row:
            resolved_source_guild_id = int(row[0])
        else:
            cur.execute("SELECT guild_id FROM rank_options LIMIT 1")
            row = cur.fetchone()
            if row:
                resolved_source_guild_id = int(row[0])

    if resolved_source_guild_id is None:
        resolved_source_guild_id = target_guild_id

    imported_config = False
    if "guild_config" in tables:
        cur.execute(
            """
            SELECT request_channel_id, approval_channel_id, staff_role_id, unverified_role_id
            FROM guild_config
            WHERE guild_id = ?
            """,
            (resolved_source_guild_id,),
        )
        row = cur.fetchone()
        if row:
            set_guild_config(
                target_guild_id,
                request_channel_id=row[0],
                approval_channel_id=row[1],
                staff_role_id=row[2],
                unverified_role_id=row[3],
            )
            imported_config = True

    imported_ranks = 0
    if "rank_options" in tables:
        cur.execute(
            "SELECT name, role_id FROM rank_options WHERE guild_id = ?",
            (resolved_source_guild_id,),
        )
        for row in cur.fetchall():
            add_rank_option(target_guild_id, row["name"], int(row["role_id"]))
            imported_ranks += 1

    src.close()
    return resolved_source_guild_id, imported_config, imported_ranks


def get_recruit(guild_id: int, user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT player_name, player_id, rank_name, rank_role_id, nickname, approved, submitted_at
        FROM recruits
        WHERE guild_id = ? AND user_id = ?
        """,
        (guild_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def upsert_recruit(
    guild_id: int,
    user_id: int,
    player_name: str,
    player_id: str,
    rank_name: str | None,
    rank_role_id: int | None,
    nickname: str = "",
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO recruits
        (guild_id, user_id, player_name, player_id, rank_name, rank_role_id, nickname, approved, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (guild_id, user_id, player_name, player_id, rank_name, rank_role_id, nickname, int(time.time())),
    )
    conn.commit()
    conn.close()


def approve_user(guild_id: int, user_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE recruits SET approved = 1 WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()


def set_recruit_rank(guild_id: int, user_id: int, rank_name: str, rank_role_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE recruits SET rank_name = ?, rank_role_id = ? WHERE guild_id = ? AND user_id = ?",
        (rank_name, rank_role_id, guild_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_user(guild_id: int, user_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM recruits WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    conn.commit()
    conn.close()


def is_configured(guild_id: int) -> bool:
    cfg = get_guild_config(guild_id)
    return bool(cfg["request_channel_id"] and cfg["approval_channel_id"] and cfg["staff_role_id"])


def setup_status_embed(guild: discord.Guild) -> discord.Embed:
    cfg = get_guild_config(guild.id)
    rank_count = len(get_rank_options(guild.id))

    def channel_mention(cid):
        return f"<#{cid}>" if cid else "Not set"

    def role_mention(rid):
        return f"<@&{rid}>" if rid else "Not set"

    embed = discord.Embed(title="RecruitBot Setup Status", color=discord.Color.blurple())
    embed.add_field(name="Request Channel", value=channel_mention(cfg["request_channel_id"]), inline=False)
    embed.add_field(name="Approval Channel", value=channel_mention(cfg["approval_channel_id"]), inline=False)
    embed.add_field(name="Staff Role", value=role_mention(cfg["staff_role_id"]), inline=False)
    embed.add_field(name="Unverified Role", value=role_mention(cfg["unverified_role_id"]), inline=False)
    embed.add_field(name="Rank Options", value=str(rank_count), inline=False)
    embed.set_footer(text="Configure channels/roles with /setup and rank options with /rank-add.")
    return embed


class ApprovalRankSelect(discord.ui.Select):
    def __init__(self, parent_view: "StaffApprovalView", rank_rows: list[tuple[str, int]]):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=name[:100], value=f"{name}|{role_id}")
            for name, role_id in rank_rows[:25]
        ]
        super().__init__(placeholder="Admin: choose rank before approving", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view._can_review(interaction):
            await interaction.response.send_message("Only staff/admin can select the approval rank.", ephemeral=True)
            return

        rank_name, role_id = self.values[0].rsplit("|", 1)
        self.parent_view.selected_rank_name = rank_name
        self.parent_view.selected_rank_role_id = int(role_id)
        await interaction.response.send_message(
            f"Selected rank for this request: **{rank_name}**",
            ephemeral=True,
        )


class RecruitForm(discord.ui.Modal, title="Recruit Request"):
    player_name = discord.ui.TextInput(label="Player Name", max_length=64, required=True)
    player_id = discord.ui.TextInput(label="Player ID", max_length=64, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        if not is_configured(interaction.guild_id):
            await interaction.response.send_message(
                "RecruitBot is not configured yet. Ask staff to run /setup.",
                ephemeral=True,
            )
            return

        rank_rows = get_rank_options(interaction.guild_id)
        if not rank_rows:
            await interaction.response.send_message(
                "No rank options are configured. Ask staff to run /rank-add.",
                ephemeral=True,
            )
            return

        existing = get_recruit(interaction.guild_id, interaction.user.id)
        now = int(time.time())
        if existing and existing[5] == 0 and now - int(existing[6] or 0) < RESUBMIT_SECONDS:
            wait_for = RESUBMIT_SECONDS - (now - int(existing[6] or 0))
            await interaction.response.send_message(
                f"You already submitted a request. Try again in {wait_for} seconds.",
                ephemeral=True,
            )
            return

        if existing and existing[5] == 1:
            await interaction.response.send_message("You are already approved.", ephemeral=True)
            return

        upsert_recruit(
            interaction.guild_id,
            interaction.user.id,
            str(self.player_name),
            str(self.player_id),
            None,
            None,
            "",
        )

        cfg = get_guild_config(interaction.guild_id)
        approval_channel = interaction.guild.get_channel(int(cfg["approval_channel_id"])) if cfg["approval_channel_id"] else None
        if not isinstance(approval_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Request saved, but approval channel is missing. Ask staff to run /setup channels.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="Recruit Request", color=discord.Color.orange())
        embed.add_field(name="Member", value=interaction.user.mention, inline=False)
        embed.add_field(name="Player", value=str(self.player_name), inline=True)
        embed.add_field(name="Player ID", value=str(self.player_id), inline=True)
        embed.add_field(name="Selected Rank", value="Pending staff selection", inline=True)
        embed.set_footer(text=f"Guild {interaction.guild_id} | User {interaction.user.id}")

        view = StaffApprovalView(interaction.guild_id, interaction.user.id)
        await approval_channel.send(embed=embed, view=view)
        await interaction.response.send_message("Request submitted. Staff will review it in the approval channel.", ephemeral=True)


class MainButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Recruit Rank",
        style=discord.ButtonStyle.blurple,
        custom_id="main_request_set_button",
    )
    async def request_set(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RecruitForm())


class StaffApprovalView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=REQUEST_EXPIRY_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.selected_rank_name: str | None = None
        self.selected_rank_role_id: int | None = None

        rank_rows = get_rank_options(guild_id)
        if rank_rows:
            self.add_item(ApprovalRankSelect(self, rank_rows))

    def _can_review(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        cfg = get_guild_config(interaction.guild_id)
        if interaction.user.guild_permissions.administrator:
            return True
        staff_role_id = cfg.get("staff_role_id")
        return bool(staff_role_id and any(r.id == int(staff_role_id) for r in interaction.user.roles))

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._can_review(interaction):
            await interaction.response.send_message("You do not have permission to approve requests.", ephemeral=True)
            return

        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("Guild mismatch for this request.", ephemeral=True)
            return

        recruit = get_recruit(self.guild_id, self.user_id)
        if not recruit:
            await interaction.response.send_message("Request record was not found.", ephemeral=True)
            return

        if not self.selected_rank_name or not self.selected_rank_role_id:
            await interaction.response.send_message(
                "Select a rank from the dropdown first, then click Approve.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("User is no longer in this server.", ephemeral=True)
            return

        cfg = get_guild_config(self.guild_id)
        rank_role = interaction.guild.get_role(int(self.selected_rank_role_id))
        if not rank_role:
            await interaction.response.send_message(
                "Selected rank role no longer exists. Choose another rank.",
                ephemeral=True,
            )
            return
        if rank_role:
            await member.add_roles(rank_role, reason="Recruit request approved")

        if cfg.get("unverified_role_id"):
            unverified_role = interaction.guild.get_role(int(cfg["unverified_role_id"]))
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="Recruit approved")

        set_recruit_rank(self.guild_id, self.user_id, self.selected_rank_name, self.selected_rank_role_id)
        approve_user(self.guild_id, self.user_id)

        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.green()
        embed.set_field_at(3, name="Selected Rank", value=self.selected_rank_name, inline=True)
        embed.add_field(name="Approved", value=f"by {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._can_review(interaction):
            await interaction.response.send_message("You do not have permission to deny requests.", ephemeral=True)
            return

        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("Guild mismatch for this request.", ephemeral=True)
            return

        delete_user(self.guild_id, self.user_id)

        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.red()
        embed.add_field(name="Denied", value=f"by {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)


class RecruitBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents)

    async def setup_hook(self):
        setup_db()
        self.add_view(MainButton())
        await self.tree.sync()
        log.info("Synced RecruitBot application commands")


bot = RecruitBot()
setup_group = app_commands.Group(name="setup", description="Configure RecruitBot")


@setup_group.command(name="channels", description="Set request and approval channels")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(request_channel="Where members submit recruit requests")
@app_commands.describe(approval_channel="Where staff approve/deny requests")
async def setup_channels(
    interaction: discord.Interaction,
    request_channel: discord.TextChannel,
    approval_channel: discord.TextChannel,
):
    await interaction.response.defer(ephemeral=True)
    set_guild_config(
        interaction.guild_id,
        request_channel_id=request_channel.id,
        approval_channel_id=approval_channel.id,
    )
    await interaction.followup.send(
        f"Configured channels. Requests: {request_channel.mention} | Approvals: {approval_channel.mention}",
        ephemeral=True,
    )


@setup_group.command(name="roles", description="Set staff and unverified roles")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(
    interaction: discord.Interaction,
    staff_role: discord.Role,
    unverified_role: discord.Role,
):
    await interaction.response.defer(ephemeral=True)
    set_guild_config(
        interaction.guild_id,
        staff_role_id=staff_role.id,
        unverified_role_id=unverified_role.id,
    )
    await interaction.followup.send(
        f"Configured roles. Staff: {staff_role.mention} | Unverified: {unverified_role.mention}",
        ephemeral=True,
    )


@setup_group.command(name="request-set", description="Post the recruit request button panel")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel="Channel to post the request panel in")
async def request_set(interaction: discord.Interaction, channel: discord.TextChannel | None = None):
    await interaction.response.defer(ephemeral=True)
    target_channel = channel or interaction.channel
    if not isinstance(target_channel, discord.TextChannel):
        await interaction.followup.send("Choose a text channel for the panel.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Recruit Request Panel",
        description="Click the button below to submit your recruit information.",
        color=discord.Color.blurple(),
    )
    await target_channel.send(embed=embed, view=MainButton())
    await interaction.followup.send(f"Request panel posted in {target_channel.mention}.", ephemeral=True)


@setup_group.command(name="status", description="Show RecruitBot configuration status")
@app_commands.checks.has_permissions(administrator=True)
async def setup_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(embed=setup_status_embed(interaction.guild), ephemeral=True)


@setup_group.command(name="import-backup", description="Import setup config and ranks from a backup recruits.db")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(source_path="Optional file path. Defaults to known backup locations.")
@app_commands.describe(source_guild_id="Optional guild ID from backup to import from.")
async def import_backup(
    interaction: discord.Interaction,
    source_path: str | None = None,
    source_guild_id: app_commands.Range[int, 1, 900719925474099] | None = None,
):
    await interaction.response.defer(ephemeral=True)
    backup_path = resolve_backup_db_path(source_path)
    if not backup_path:
        await interaction.followup.send(
            "No backup database found. Put a file at `RecruitBot/recruits_backup.db` or pass a path.",
            ephemeral=True,
        )
        return

    try:
        used_guild_id, imported_config, imported_ranks = import_backup_for_guild(
            source_db_path=backup_path,
            target_guild_id=interaction.guild_id,
            source_guild_id=source_guild_id,
        )
    except ValueError as e:
        await interaction.followup.send(f"Import failed: {e}", ephemeral=True)
        return
    except sqlite3.Error as e:
        await interaction.followup.send(f"Database import error: {e}", ephemeral=True)
        return

    config_msg = "yes" if imported_config else "no"
    await interaction.followup.send(
        "\n".join(
            [
                "Recruit backup import complete.",
                f"Source DB: `{backup_path}`",
                f"Source guild ID: `{used_guild_id}`",
                f"Imported config: `{config_msg}`",
                f"Imported rank options: `{imported_ranks}`",
            ]
        ),
        ephemeral=True,
    )


@bot.tree.command(name="rank-add", description="Add a selectable recruit rank option")
@app_commands.checks.has_permissions(administrator=True)
async def rank_add(interaction: discord.Interaction, rank: str, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    add_rank_option(interaction.guild_id, rank, role.id)
    await interaction.followup.send(f"Added rank option **{rank}** -> {role.mention}", ephemeral=True)


@bot.tree.command(name="rank-remove", description="Remove a selectable recruit rank option")
@app_commands.checks.has_permissions(administrator=True)
async def rank_remove(interaction: discord.Interaction, rank: str):
    await interaction.response.defer(ephemeral=True)
    deleted = remove_rank_option(interaction.guild_id, rank)
    if not deleted:
        await interaction.followup.send(f"Rank **{rank}** was not found.", ephemeral=True)
        return
    await interaction.followup.send(f"Removed rank option **{rank}**.", ephemeral=True)


@bot.tree.command(name="ranks", description="View configured recruit rank options")
async def ranks(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    rows = get_rank_options(interaction.guild_id)
    if not rows:
        await interaction.followup.send("No rank options configured yet.", ephemeral=True)
        return

    embed = discord.Embed(title="Recruit Rank Options", color=discord.Color.blurple())
    for name, role_id in rows:
        embed.add_field(name=name, value=f"<@&{role_id}>", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="recruit_ping", description="Check if RecruitBot is online")
async def recruit_ping(interaction: discord.Interaction):
    await interaction.response.send_message("RecruitBot is online.", ephemeral=True)


@bot.event
async def on_guild_join(guild: discord.Guild):
    set_guild_config(guild.id)


@bot.event
async def on_member_join(member: discord.Member):
    cfg = get_guild_config(member.guild.id)
    if cfg.get("unverified_role_id"):
        role = member.guild.get_role(int(cfg["unverified_role_id"]))
        if role:
            try:
                await member.add_roles(role, reason="RecruitBot auto-assign unverified role")
            except discord.Forbidden:
                pass


@bot.event
async def on_member_remove(member: discord.Member):
    delete_user(member.guild.id, member.id)


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)


@setup_channels.error
@setup_roles.error
@request_set.error
@setup_status.error
@import_backup.error
@rank_add.error
@rank_remove.error
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception("RecruitBot command error", exc_info=error)

    if isinstance(error, app_commands.MissingPermissions):
        if interaction.response.is_done():
            await interaction.followup.send("You need administrator permission to use this.", ephemeral=True)
        else:
            await interaction.response.send_message("You need administrator permission to use this.", ephemeral=True)
        return

    if isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        msg = f"RecruitBot is missing permissions: {perms}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Command is on cooldown. Try again in {error.retry_after:.1f}s."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    msg = f"RecruitBot command failed: {type(error).__name__}"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global fallback so slash-command failures never look like silent timeouts."""
    log.exception("RecruitBot tree error", exc_info=error)

    if isinstance(error, app_commands.CommandInvokeError) and error.original:
        detail = f"{type(error.original).__name__}: {error.original}"
    else:
        detail = f"{type(error).__name__}: {error}"

    msg = f"RecruitBot error: {detail[:1800]}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        # Last-resort: never crash the handler itself.
        log.exception("Failed to send tree error response")


bot.tree.add_command(setup_group)


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
