"""Household snapshot utils"""

from datetime import datetime, timezone
from typing import List, Tuple, Any, Optional
from app.database.models import ApplianceInDB


def serialize_appliance_snapshot(appliance: ApplianceInDB) -> Tuple[Any, ...]:
    """
    Single source of truth helper defining the tuple of all AI-relevant properties
    of an appliance that influence recommendations.
    """
    return (
        appliance.id,
        appliance.name,
        appliance.category,
        float(appliance.wattage_watts),
        float(appliance.daily_usage_hours),
        bool(appliance.is_active),
    )


def generate_household_snapshot_version(appliances: List[ApplianceInDB]) -> str:
    """
    Generates a deterministic, human-readable snapshot version string from all active appliances.
    Sorts active appliances by ID and joins their serialized tuples.
    """
    active_appliances = [app for app in appliances if app.is_active]
    sorted_appliances = sorted(active_appliances, key=lambda app: app.id)

    serialized_items = []
    for app in sorted_appliances:
        serialized_tuple = serialize_appliance_snapshot(app)
        # Join tuple elements as strings
        item_str = ":".join(str(val) for val in serialized_tuple)
        serialized_items.append(item_str)

    return "|".join(serialized_items)


def format_cooldown_time_remaining(
    next_allowed: datetime, now: Optional[datetime] = None
) -> str:
    """
    Formats the remaining time until next_allowed into a human-readable string
    (e.g., '23 hours and 45 minutes', '15 minutes', '1 minute', '45 seconds').
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if next_allowed.tzinfo is None:
        next_allowed = next_allowed.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    total_seconds = int((next_allowed - now).total_seconds())
    if total_seconds <= 0:
        return "0 seconds"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts or (hours == 0 and minutes == 0 and seconds > 0):
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " and ".join(parts)
