from datetime import datetime, timezone


def money(amount: float) -> str:
    """Format a number as currency, e.g. 1500000 -> $1,500,000."""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(round(amount)):,}"


def percent(value: float) -> str:
    if value == int(value):
        return f"{int(value)}%"
    return f"{value:g}%"


def progress_bar(current: float, target: float, length: int = 12) -> str:
    """Render a block-emoji progress bar with a percentage label."""
    if target <= 0:
        ratio = 1.0
    else:
        ratio = max(0.0, min(1.0, current / target))
    filled = round(ratio * length)
    bar = "🟩" * filled + "⬛" * (length - filled)
    return f"{bar} `{ratio * 100:.1f}%`"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def discord_timestamp(dt: datetime, style: str = "f") -> str:
    """Discord's dynamic <t:epoch:style> timestamp markup."""
    return f"<t:{int(dt.timestamp())}:{style}>"


def rank_medal(position: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"`#{position}`")


def truncate(text: str, length: int = 100) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"
