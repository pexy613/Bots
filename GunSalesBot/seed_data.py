"""Initial weapon catalog seeded into a guild the first time the bot sees it."""

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
