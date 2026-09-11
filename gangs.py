import re

import database


def normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _clean_display(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def resolve_gang_name(guild_id: int, raw_name: str) -> str:
    """Map a typed gang name to its canonical form, registering it if new.

    Case and surrounding/repeated whitespace are folded together so
    "Vagos", "vagos", and "  Vagos  " always resolve to the same
    canonical entry. A brand-new spelling is registered as-is and
    becomes the canonical form for that spelling going forward.
    """
    key = normalize_key(raw_name)
    if not key:
        return _clean_display(raw_name)

    alias_row = database.fetchone(
        "SELECT canonical_name FROM gang_aliases WHERE guild_id = ? AND alias_key = ?",
        (guild_id, key)
    )
    if alias_row:
        return alias_row[0]

    gang_row = database.fetchone(
        "SELECT canonical_name FROM gangs WHERE guild_id = ? AND name_key = ?",
        (guild_id, key)
    )
    if gang_row:
        return gang_row[0]

    canonical_name = _clean_display(raw_name)
    database.execute(
        "INSERT OR IGNORE INTO gangs (guild_id, canonical_name, name_key) VALUES (?, ?, ?)",
        (guild_id, canonical_name, key)
    )
    return canonical_name


def list_known_gangs(guild_id: int, limit: int = 24):
    """Registered gangs for a guild, most active first."""
    rows = database.fetchall("""
        SELECT g.canonical_name, COUNT(w.id) AS wash_count
        FROM gangs g
        LEFT JOIN washes w
            ON w.guild_id = g.guild_id AND w.gang_name = g.canonical_name
        WHERE g.guild_id = ?
        GROUP BY g.canonical_name
        ORDER BY wash_count DESC, g.canonical_name COLLATE NOCASE ASC
        LIMIT ?
    """, (guild_id, limit))
    return [row[0] for row in rows]


def add_alias(guild_id: int, alias: str, canonical_name: str) -> str:
    """Register a shortcut (e.g. "cfc") that resolves to an existing/new gang."""
    resolved_canonical = resolve_gang_name(guild_id, canonical_name)
    alias_key = normalize_key(alias)
    alias_display = _clean_display(alias)
    database.execute(
        "INSERT OR REPLACE INTO gang_aliases (guild_id, alias_key, alias_display, canonical_name) VALUES (?, ?, ?, ?)",
        (guild_id, alias_key, alias_display, resolved_canonical)
    )
    return resolved_canonical


def list_aliases(guild_id: int):
    rows = database.fetchall(
        "SELECT alias_display, canonical_name FROM gang_aliases WHERE guild_id = ? ORDER BY alias_display COLLATE NOCASE ASC",
        (guild_id,)
    )
    return [(row[0], row[1]) for row in rows]


def merge_gang(guild_id: int, from_name: str, into_name: str) -> str:
    """Fold every wash logged under from_name (any case/spacing variant) into into_name."""
    into_canonical = resolve_gang_name(guild_id, into_name)
    from_key = normalize_key(from_name)

    variants = database.fetchall(
        "SELECT DISTINCT gang_name FROM washes WHERE guild_id = ? AND gang_name IS NOT NULL",
        (guild_id,)
    )
    for (variant,) in variants:
        if variant != into_canonical and normalize_key(variant) == from_key:
            database.execute(
                "UPDATE washes SET gang_name = ? WHERE guild_id = ? AND gang_name = ?",
                (into_canonical, guild_id, variant)
            )

    gang_rows = database.fetchall(
        "SELECT canonical_name FROM gangs WHERE guild_id = ?",
        (guild_id,)
    )
    for (variant,) in gang_rows:
        if variant != into_canonical and normalize_key(variant) == from_key:
            database.execute(
                "DELETE FROM gangs WHERE guild_id = ? AND canonical_name = ?",
                (guild_id, variant)
            )

    database.execute(
        "UPDATE gang_aliases SET canonical_name = ? WHERE guild_id = ? AND canonical_name = ?",
        (into_canonical, guild_id, from_name)
    )

    return into_canonical


def remove_gang(guild_id: int, gang_name: str) -> str | None:
    """Remove a gang from the picker list. Past wash history keeps its logged
    gang_name untouched — this only stops the gang from being offered again."""
    key = normalize_key(gang_name)

    gang_rows = database.fetchall(
        "SELECT canonical_name FROM gangs WHERE guild_id = ?",
        (guild_id,)
    )
    match = next((name for (name,) in gang_rows if normalize_key(name) == key), None)
    if match is None:
        return None

    database.execute(
        "DELETE FROM gangs WHERE guild_id = ? AND canonical_name = ?",
        (guild_id, match)
    )
    return match
