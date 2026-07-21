from datetime import datetime


def format_money(amount: int | float) -> str:
    return f"{int(amount):,}"


def is_management(member) -> bool:
    return any("management" in role.name.lower() for role in getattr(member, "roles", []))


def is_admin(member) -> bool:
    permissions = getattr(member, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def can_manage(member) -> bool:
    return is_admin(member) or is_management(member)


def find_channel(guild, keyword: str):
    if guild is None:
        return None
    keyword = keyword.lower()
    for channel in guild.text_channels:
        if keyword in channel.name.lower():
            return channel
    return None


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %I:%M %p")
