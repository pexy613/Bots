import os
from typing import Any, Optional

import aiosqlite

from .config import DB_PATH, DEFAULT_COMMISSION_PERCENT
from .utils.formatting import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    guild_id TEXT PRIMARY KEY,
    commission_percent REAL NOT NULL DEFAULT 20,
    log_channel_id TEXT,
    leaderboard_channel_id TEXT,
    leaderboard_message_id TEXT,
    dashboard_channel_id TEXT,
    dashboard_message_id TEXT
);

CREATE TABLE IF NOT EXISTS guns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    price INTEGER NOT NULL,
    discount_percent REAL NOT NULL DEFAULT 25,
    emoji TEXT NOT NULL DEFAULT '🔫',
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    gun_name TEXT NOT NULL,
    category TEXT,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    price_type TEXT NOT NULL,
    total_amount INTEGER NOT NULL,
    commission_percent REAL NOT NULL,
    profit INTEGER NOT NULL,
    seller_id TEXT NOT NULL,
    seller_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target_amount INTEGER NOT NULL,
    metric TEXT NOT NULL DEFAULT 'revenue',
    start_at TEXT NOT NULL,
    end_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    panel_channel_id TEXT,
    panel_message_id TEXT
);
"""


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()

    async def _table_columns(self, table: str) -> set:
        cur = await self._conn.execute(f"PRAGMA table_info({table})")
        rows = await cur.fetchall()
        return {r["name"] for r in rows}

    async def _migrate(self):
        """Bring older on-disk databases up to date with the current SCHEMA."""
        sales_cols = await self._table_columns("sales")
        if "buyer" in sales_cols:
            try:
                await self._conn.execute("ALTER TABLE sales DROP COLUMN buyer")
            except aiosqlite.OperationalError:
                pass  # SQLite too old to support DROP COLUMN; harmless leftover column.

        settings_cols = await self._table_columns("settings")
        if "leaderboard_channel_id" not in settings_cols:
            await self._conn.execute("ALTER TABLE settings ADD COLUMN leaderboard_channel_id TEXT")
        if "leaderboard_message_id" not in settings_cols:
            await self._conn.execute("ALTER TABLE settings ADD COLUMN leaderboard_message_id TEXT")
        if "dashboard_channel_id" not in settings_cols:
            await self._conn.execute("ALTER TABLE settings ADD COLUMN dashboard_channel_id TEXT")
        if "dashboard_message_id" not in settings_cols:
            await self._conn.execute("ALTER TABLE settings ADD COLUMN dashboard_message_id TEXT")

        goals_cols = await self._table_columns("goals")
        if "panel_channel_id" not in goals_cols:
            await self._conn.execute("ALTER TABLE goals ADD COLUMN panel_channel_id TEXT")
        if "panel_message_id" not in goals_cols:
            await self._conn.execute("ALTER TABLE goals ADD COLUMN panel_message_id TEXT")

    async def close(self):
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database not connected"
        return self._conn

    # ---------- settings ----------

    async def get_settings(self, guild_id: str) -> aiosqlite.Row:
        cur = await self.conn.execute("SELECT * FROM settings WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        if row is None:
            await self.conn.execute(
                "INSERT INTO settings (guild_id, commission_percent) VALUES (?, ?)",
                (guild_id, DEFAULT_COMMISSION_PERCENT),
            )
            await self.conn.commit()
            cur = await self.conn.execute("SELECT * FROM settings WHERE guild_id = ?", (guild_id,))
            row = await cur.fetchone()
        return row

    async def set_commission(self, guild_id: str, percent: float):
        await self.get_settings(guild_id)
        await self.conn.execute(
            "UPDATE settings SET commission_percent = ? WHERE guild_id = ?", (percent, guild_id)
        )
        await self.conn.commit()

    async def set_log_channel(self, guild_id: str, channel_id: Optional[str]):
        await self.get_settings(guild_id)
        await self.conn.execute(
            "UPDATE settings SET log_channel_id = ? WHERE guild_id = ?", (channel_id, guild_id)
        )
        await self.conn.commit()

    async def set_leaderboard_panel(
        self, guild_id: str, channel_id: Optional[str], message_id: Optional[str]
    ):
        await self.get_settings(guild_id)
        await self.conn.execute(
            "UPDATE settings SET leaderboard_channel_id = ?, leaderboard_message_id = ? WHERE guild_id = ?",
            (channel_id, message_id, guild_id),
        )
        await self.conn.commit()

    async def set_dashboard_panel(
        self, guild_id: str, channel_id: Optional[str], message_id: Optional[str]
    ):
        await self.get_settings(guild_id)
        await self.conn.execute(
            "UPDATE settings SET dashboard_channel_id = ?, dashboard_message_id = ? WHERE guild_id = ?",
            (channel_id, message_id, guild_id),
        )
        await self.conn.commit()

    # ---------- guns ----------

    async def add_gun(
        self,
        guild_id: str,
        name: str,
        price: int,
        discount_percent: float,
        category: Optional[str],
        emoji: str,
    ):
        await self.conn.execute(
            """INSERT INTO guns (guild_id, name, category, price, discount_percent, emoji)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, name, category, price, discount_percent, emoji),
        )
        await self.conn.commit()

    async def edit_gun(self, guild_id: str, name: str, **fields: Any) -> bool:
        if not fields:
            return False
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [guild_id, name]
        cur = await self.conn.execute(
            f"UPDATE guns SET {columns} WHERE guild_id = ? AND name = ?", values
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def remove_gun(self, guild_id: str, name: str) -> bool:
        cur = await self.conn.execute(
            "UPDATE guns SET active = 0 WHERE guild_id = ? AND name = ?", (guild_id, name)
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def get_gun(self, guild_id: str, name: str) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM guns WHERE guild_id = ? AND name = ? AND active = 1", (guild_id, name)
        )
        return await cur.fetchone()

    async def get_gun_ci(self, guild_id: str, name: str) -> Optional[aiosqlite.Row]:
        """Case-insensitive lookup, for free-typed input like the sale modal."""
        cur = await self.conn.execute(
            "SELECT * FROM guns WHERE guild_id = ? AND active = 1 AND LOWER(name) = LOWER(?)",
            (guild_id, name),
        )
        return await cur.fetchone()

    async def list_guns(self, guild_id: str, active_only: bool = True) -> list[aiosqlite.Row]:
        query = "SELECT * FROM guns WHERE guild_id = ?"
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY category IS NULL, category, price DESC"
        cur = await self.conn.execute(query, (guild_id,))
        return await cur.fetchall()

    async def gun_name_choices(self, guild_id: str, prefix: str) -> list[str]:
        cur = await self.conn.execute(
            "SELECT name FROM guns WHERE guild_id = ? AND active = 1 AND name LIKE ? ORDER BY name LIMIT 25",
            (guild_id, f"%{prefix}%"),
        )
        rows = await cur.fetchall()
        return [r["name"] for r in rows]

    # ---------- sales ----------

    async def add_sale(
        self,
        guild_id: str,
        gun_name: str,
        category: Optional[str],
        quantity: int,
        unit_price: int,
        price_type: str,
        total_amount: int,
        commission_percent: float,
        profit: int,
        seller_id: str,
        seller_name: str,
    ) -> int:
        cur = await self.conn.execute(
            """INSERT INTO sales
               (guild_id, gun_name, category, quantity, unit_price, price_type, total_amount,
                commission_percent, profit, seller_id, seller_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                guild_id,
                gun_name,
                category,
                quantity,
                unit_price,
                price_type,
                total_amount,
                commission_percent,
                profit,
                seller_id,
                seller_name,
                now_iso(),
            ),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_sale(self, sale_id: int) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,))
        return await cur.fetchone()

    async def update_sale(self, sale_id: int, **fields: Any) -> bool:
        if not fields:
            return False
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [sale_id]
        cur = await self.conn.execute(f"UPDATE sales SET {columns} WHERE id = ?", values)
        await self.conn.commit()
        return cur.rowcount > 0

    async def delete_sale(self, sale_id: int) -> bool:
        cur = await self.conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_sales(
        self,
        guild_id: str,
        since: Optional[str] = None,
        seller_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[aiosqlite.Row]:
        query = "SELECT * FROM sales WHERE guild_id = ?"
        params: list[Any] = [guild_id]
        if since:
            query += " AND created_at >= ?"
            params.append(since)
        if seller_id:
            query += " AND seller_id = ?"
            params.append(seller_id)
        query += " ORDER BY created_at DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cur = await self.conn.execute(query, params)
        return await cur.fetchall()

    async def stats(
        self, guild_id: str, since: Optional[str] = None, seller_id: Optional[str] = None
    ) -> dict:
        query = (
            "SELECT COALESCE(SUM(total_amount), 0) AS washed, "
            "COALESCE(SUM(profit), 0) AS profit, COUNT(*) AS count "
            "FROM sales WHERE guild_id = ?"
        )
        params: list[Any] = [guild_id]
        if since:
            query += " AND created_at >= ?"
            params.append(since)
        if seller_id:
            query += " AND seller_id = ?"
            params.append(seller_id)
        cur = await self.conn.execute(query, params)
        row = await cur.fetchone()
        return {"washed": row["washed"], "profit": row["profit"], "count": row["count"]}

    async def leaderboard(
        self,
        guild_id: str,
        since: Optional[str] = None,
        metric: str = "washed",
        limit: int = 10,
    ) -> list[aiosqlite.Row]:
        order_col = {"washed": "washed", "profit": "profit", "count": "count"}.get(metric, "washed")
        query = (
            "SELECT seller_id, seller_name, COALESCE(SUM(total_amount), 0) AS washed, "
            "COALESCE(SUM(profit), 0) AS profit, COUNT(*) AS count "
            "FROM sales WHERE guild_id = ?"
        )
        params: list[Any] = [guild_id]
        if since:
            query += " AND created_at >= ?"
            params.append(since)
        query += f" GROUP BY seller_id, seller_name ORDER BY {order_col} DESC LIMIT ?"
        params.append(limit)
        cur = await self.conn.execute(query, params)
        return await cur.fetchall()

    # ---------- goals ----------

    async def create_goal(
        self,
        guild_id: str,
        name: str,
        target_amount: int,
        metric: str,
        end_at: Optional[str],
        created_by: str,
    ) -> int:
        await self.conn.execute(
            "UPDATE goals SET active = 0 WHERE guild_id = ? AND active = 1", (guild_id,)
        )
        cur = await self.conn.execute(
            """INSERT INTO goals (guild_id, name, target_amount, metric, start_at, end_at, active, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (guild_id, name, target_amount, metric, now_iso(), end_at, created_by),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_active_goal(self, guild_id: str) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM goals WHERE guild_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
            (guild_id,),
        )
        return await cur.fetchone()

    async def end_goal(self, goal_id: int) -> bool:
        cur = await self.conn.execute("UPDATE goals SET active = 0 WHERE id = ?", (goal_id,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_goal_panel(self, goal_id: int, channel_id: Optional[str], message_id: Optional[str]):
        await self.conn.execute(
            "UPDATE goals SET panel_channel_id = ?, panel_message_id = ? WHERE id = ?",
            (channel_id, message_id, goal_id),
        )
        await self.conn.commit()

    async def list_goals(self, guild_id: str, limit: int = 10) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM goals WHERE guild_id = ? ORDER BY id DESC LIMIT ?", (guild_id, limit)
        )
        return await cur.fetchall()

    async def goal_current_amount(self, goal: aiosqlite.Row) -> float:
        query = (
            "SELECT COALESCE(SUM(total_amount), 0) AS washed, COUNT(*) AS count "
            "FROM sales WHERE guild_id = ? AND created_at >= ?"
        )
        params: list[Any] = [goal["guild_id"], goal["start_at"]]
        if goal["end_at"]:
            query += " AND created_at <= ?"
            params.append(goal["end_at"])
        cur = await self.conn.execute(query, params)
        row = await cur.fetchone()
        return row["count"] if goal["metric"] == "count" else row["washed"]
