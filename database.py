import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "laundering.db")

# Guild ID that pre-migration (single-server) data gets attached to.
LEGACY_GUILD_ID = 1512987024695623861


def get_connection():
    return sqlite3.connect(DB_NAME)


def _column_names(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS washes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL DEFAULT 0,
        user TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        amount_washed INTEGER NOT NULL,
        percentage_taken REAL NOT NULL,
        profit_taken INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    if "guild_id" not in _column_names(cursor, "washes"):
        cursor.execute("ALTER TABLE washes ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")
        cursor.execute("UPDATE washes SET guild_id = ? WHERE guild_id = 0", (LEGACY_GUILD_ID,))

    if "amount_deposited" in _column_names(cursor, "washes"):
        cursor.execute("ALTER TABLE washes DROP COLUMN amount_deposited")

    if _table_exists(cursor, "settings") and "guild_id" not in _column_names(cursor, "settings"):
        cursor.execute("ALTER TABLE settings RENAME TO settings_legacy")
        cursor.execute("""
        CREATE TABLE settings (
            guild_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        )
        """)
        cursor.execute("""
            INSERT INTO settings (guild_id, key, value)
            SELECT ?, key, value FROM settings_legacy
        """, (LEGACY_GUILD_ID,))
        cursor.execute("DROP TABLE settings_legacy")
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        )
        """)

    conn.commit()
    conn.close()


def execute(query: str, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()


def fetchone(query: str, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row


def fetchall(query: str, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_setting(guild_id: int, key: str, value: str):
    execute(
        "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
        (guild_id, key, value)
    )


def get_setting(guild_id: int, key: str):
    row = fetchone("SELECT value FROM settings WHERE guild_id = ? AND key = ?", (guild_id, key))
    return row[0] if row else None
