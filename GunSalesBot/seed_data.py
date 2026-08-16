"""Initial weapon catalog seeded into a guild the first time the bot sees it."""

from .supabase_mirror import supabase_upsert_gun

DEFAULT_CATALOG = [
    {"name": "AK74", "price": 230_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "AP Pistol", "price": 15_000_000, "category": "Pistol", "emoji": "🔫"},
    {"name": "AWM Magnum", "price": 3_000_000, "category": "Sniper", "emoji": "🔭"},
    {"name": "Desert Eagle", "price": 700_000, "category": "Pistol", "emoji": "🔫"},
    {"name": "FN Seven", "price": 130_000, "category": "Pistol", "emoji": "🔫"},
    {"name": "G3", "price": 260_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "M16", "price": 400_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "M1911", "price": 150_000, "category": "Pistol", "emoji": "🔫"},
    {"name": "M249", "price": 2_000_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "Mossberg Shotgun", "price": 1_000_000, "category": "Shotgun", "emoji": "💥"},
    {"name": "MTAR 21", "price": 300_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "QBZ 95", "price": 700_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "Sig Sauer 556", "price": 260_000, "category": "Rifle", "emoji": "🎯"},
    {"name": "Stun Gun", "price": 5_000_000, "category": "Special", "emoji": "⚡"},
    {"name": "Tec 9", "price": 260_000, "category": "Pistol", "emoji": "🔫"},
]

DEFAULT_DISCOUNT_PERCENT = 25.0

# Catalog-only reference items (not sold through the Log Sale dropdown) — the
# district99-rules price sheets cover chopshop, ammo, laundering, and drugs
# alongside the weapon list.
EXTRA_CATALOG = [
    {"name": "Lockpick", "price": 7_000, "category": "Chopshop", "emoji": "🔓"},
    {"name": "Card", "price": 7_000, "category": "Chopshop", "emoji": "💳"},
    {"name": "Pendrive", "price": 9_000, "category": "Chopshop", "emoji": "💾"},
    {"name": "C4", "price": 25_000, "category": "Chopshop", "emoji": "🧨"},
    {"name": "Vest", "price": 5_000, "category": "Ammo", "emoji": "🦺"},
    {"name": "Pistol Ammo (100)", "price": 120_000, "category": "Ammo", "emoji": "🟡"},
    {"name": "Shotgun Ammo", "price": 165_000, "category": "Ammo", "emoji": "🟠"},
    {"name": "Sniper Ammo (15)", "price": 700_000, "category": "Ammo", "emoji": "🟣"},
    {"name": "AR Ammo (100)", "price": 100_000, "category": "Ammo", "emoji": "🟢"},
    {"name": "SMG Ammo", "price": 120_000, "category": "Ammo", "emoji": "🔴"},
    {"name": "Handcuff", "price": 25_000, "category": "Money Laundering", "emoji": "⛓️"},
    {
        "name": "Money Laundry",
        "price": 0,
        "category": "Money Laundering",
        "emoji": "🧼",
        "price_label": "30% cut",
    },
    {"name": "Coke", "price": 15_000, "category": "Drugs", "emoji": "❄️"},
    {"name": "Joints", "price": 15_000, "category": "Drugs", "emoji": "🌿"},
    {"name": "Meth", "price": 20_000, "category": "Drugs", "emoji": "🧪"},
]


async def seed_guild(db, guild_id: str):
    existing = await db.list_guns(guild_id, active_only=False)
    if existing:
        return
    for gun in DEFAULT_CATALOG:
        await db.add_gun(
            guild_id=guild_id,
            name=gun["name"],
            price=gun["price"],
            discount_percent=DEFAULT_DISCOUNT_PERCENT,
            category=gun["category"],
            emoji=gun["emoji"],
        )
        supabase_upsert_gun(await db.get_gun_any(guild_id, gun["name"]))


async def seed_extra_items(db, guild_id: str):
    """Adds any missing catalog-only items from EXTRA_CATALOG. Runs on every
    startup but is idempotent by name, and never revives an item an admin has
    since removed (get_gun_any matches regardless of active status)."""
    for item in EXTRA_CATALOG:
        if await db.get_gun_any(guild_id, item["name"]):
            continue
        await db.add_gun(
            guild_id=guild_id,
            name=item["name"],
            price=item["price"],
            discount_percent=0,
            category=item["category"],
            emoji=item["emoji"],
            sellable=False,
            price_label=item.get("price_label"),
        )
        supabase_upsert_gun(await db.get_gun_any(guild_id, item["name"]))
