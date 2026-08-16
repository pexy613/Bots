import logging

from supabase import create_client, Client

from .config import SUPABASE_KEY, SUPABASE_URL

log = logging.getLogger("gunsales")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supabase mirror (gun_bot.*) --------------------------------------------
# Best-effort writes: the local SQLite database remains this bot's source of
# truth for live logic (receipts, leaderboards, goal progress, etc). These
# calls mirror the same events into Supabase and never raise into the caller
# if the network call fails.


def supabase_upsert_settings(settings) -> None:
    try:
        supabase.schema("gun_bot").table("settings").upsert(
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
        ).execute()
    except Exception:
        log.exception("Supabase upsert_settings failed for guild %s", settings["guild_id"])


def supabase_upsert_sale(sale) -> None:
    try:
        supabase.schema("gun_bot").table("sales").upsert(
            {
                "id": sale["id"],
                "guild_id": int(sale["guild_id"]),
                "gun_name": sale["gun_name"],
                "category": sale["category"],
                "quantity": sale["quantity"],
                "unit_price": sale["unit_price"],
                "price_type": sale["price_type"],
                "total_amount": sale["total_amount"],
                "commission_percent": sale["commission_percent"],
                "profit": sale["profit"],
                "seller_id": int(sale["seller_id"]),
                "seller_name": sale["seller_name"],
                "created_at": sale["created_at"],
            },
            on_conflict="id",
        ).execute()
    except Exception:
        log.exception("Supabase upsert_sale failed for sale #%s", sale["id"])


def supabase_delete_sale(sale_id: int) -> None:
    try:
        supabase.schema("gun_bot").table("sales").delete().eq("id", sale_id).execute()
    except Exception:
        log.exception("Supabase delete_sale failed for sale #%s", sale_id)


def supabase_upsert_gun(gun) -> None:
    if gun is None:
        return
    try:
        supabase.schema("gun_bot").table("guns").upsert(
            {
                "id": gun["id"],
                "guild_id": int(gun["guild_id"]),
                "name": gun["name"],
                "category": gun["category"],
                "price": gun["price"],
                "discount_percent": gun["discount_percent"],
                "emoji": gun["emoji"],
                "active": gun["active"],
                "sellable": gun["sellable"],
                "price_label": gun["price_label"],
            },
            on_conflict="id",
        ).execute()
    except Exception:
        log.exception("Supabase upsert_gun failed for gun #%s", gun["id"])


def supabase_upsert_goal(goal) -> None:
    if goal is None:
        return
    try:
        supabase.schema("gun_bot").table("goals").upsert(
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
        ).execute()
    except Exception:
        log.exception("Supabase upsert_goal failed for goal #%s", goal["id"])
