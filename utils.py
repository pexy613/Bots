from datetime import datetime


def format_money(amount: int | float) -> str:
    return f"{int(amount):,}"


def is_admin(member) -> bool:
    # interaction.user carries resolved_permissions straight from Discord's
    # own interaction payload, which is accurate even when the bot's local
    # guild/role cache is incomplete (guild_permissions looks up each role
    # via that cache and silently drops ones it can't find).
    resolved = getattr(member, "resolved_permissions", None)
    if resolved is not None:
        return resolved.administrator

    permissions = getattr(member, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def is_management(member) -> bool:
    if is_admin(member):
        return True
    return any("management" in role.name.lower() for role in getattr(member, "roles", []))


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
