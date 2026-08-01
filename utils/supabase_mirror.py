"""Best-effort mirror of local sales data into Supabase's gun_bot schema.

Supabase is a secondary copy for reporting/cross-bot access — the local SQLite
database is always the source of truth. Every mirror call is wrapped in its
own try/except at the call site (same pattern as RecruitBot / the wash
logger) so a Supabase hiccup never blocks or fails the user-facing command.
"""

import logging
from typing import Any, Optional

import aiohttp

from config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

log = logging.getLogger("gunsales.supabase")

SCHEMA = "gun_bot"


class SupabaseMirror:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            log.warning(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — Supabase mirroring is disabled."
            )
            return
        self._session = aiohttp.ClientSession(
            base_url=SUPABASE_URL,
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        if self._session:
            await self._session.close()

    @property
    def enabled(self) -> bool:
        return self._session is not None

    async def upsert(self, table: str, row: dict[str, Any], on_conflict: str) -> None:
        """Insert or update a single row, matched on `on_conflict` (a PK column)."""
        if not self._session:
            return
        async with self._session.post(
            f"/rest/v1/{table}",
            params={"on_conflict": on_conflict},
            headers={
                "Content-Profile": SCHEMA,
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=row,
        ) as resp:
            if resp.status >= 300:
                body = await resp.text()
                raise RuntimeError(f"Supabase upsert into {table} failed ({resp.status}): {body}")

    async def delete(self, table: str, column: str, value: Any) -> None:
        if not self._session:
            return
        async with self._session.delete(
            f"/rest/v1/{table}",
            params={column: f"eq.{value}"},
            headers={"Content-Profile": SCHEMA, "Prefer": "return=minimal"},
        ) as resp:
            if resp.status >= 300:
                body = await resp.text()
                raise RuntimeError(f"Supabase delete from {table} failed ({resp.status}): {body}")


# ---------- row-shaping helpers, one per mirrored table ----------
# Each wraps its own try/except: mirroring is best-effort and must never
# break the local write it's shadowing.


async def mirror_sale(bot, sale_id: int) -> None:
    row = await bot.db.get_sale(sale_id)
    if row is None:
        return
    try:
        await bot.supabase.upsert(
            "sales",
            {
                "id": row["id"],
                "guild_id": int(row["guild_id"]),
                "gun_name": row["gun_name"],
                "category": row["category"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "price_type": row["price_type"],
                "total_amount": row["total_amount"],
                "commission_percent": row["commission_percent"],
                "profit": row["profit"],
                "seller_id": int(row["seller_id"]),
                "seller_name": row["seller_name"],
                "created_at": row["created_at"],
            },
            on_conflict="id",
        )
    except Exception:
        log.warning("Failed to mirror sale #%s to Supabase", sale_id, exc_info=True)


async def mirror_sale_delete(bot, sale_id: int) -> None:
    try:
        await bot.supabase.delete("sales", "id", sale_id)
    except Exception:
        log.warning("Failed to mirror deletion of sale #%s to Supabase", sale_id, exc_info=True)


async def mirror_settings(bot, guild_id: str) -> None:
    settings = await bot.db.get_settings(guild_id)
    try:
        await bot.supabase.upsert(
            "settings",
            {
                "guild_id": int(settings["guild_id"]),
                "commission_percent": settings["commission_percent"],
                "log_channel_id": int(settings["log_channel_id"]) if settings["log_channel_id"] else None,
                "leaderboard_channel_id": (
                    int(settings["leaderboard_channel_id"]) if settings["leaderboard_channel_id"] else None
                ),
                "leaderboard_message_id": (
                    int(settings["leaderboard_message_id"]) if settings["leaderboard_message_id"] else None
                ),
                "dashboard_channel_id": (
                    int(settings["dashboard_channel_id"]) if settings["dashboard_channel_id"] else None
                ),
                "dashboard_message_id": (
                    int(settings["dashboard_message_id"]) if settings["dashboard_message_id"] else None
                ),
            },
            on_conflict="guild_id",
        )
    except Exception:
        log.warning("Failed to mirror settings for guild %s to Supabase", guild_id, exc_info=True)


async def mirror_goal(bot, goal) -> None:
    if goal is None:
        return
    try:
        await bot.supabase.upsert(
            "goals",
            {
                "id": goal["id"],
                "guild_id": int(goal["guild_id"]),
                "name": goal["name"],
                "target_amount": goal["target_amount"],
                "metric": goal["metric"],
                "start_at": goal["start_at"],
                "end_at": goal["end_at"],
                "active": goal["active"],
                "created_by": int(goal["created_by"]) if goal["created_by"] else None,
                "panel_channel_id": int(goal["panel_channel_id"]) if goal["panel_channel_id"] else None,
                "panel_message_id": int(goal["panel_message_id"]) if goal["panel_message_id"] else None,
            },
            on_conflict="id",
        )
    except Exception:
        log.warning("Failed to mirror goal #%s to Supabase", goal["id"], exc_info=True)
