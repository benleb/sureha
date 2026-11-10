"""Helpers for the SureHA integration."""
from __future__ import annotations

from datetime import datetime, timezone


def parse_since(since: datetime | str | None) -> datetime | None:
    """Return `since` as an aware datetime, or None if missing/invalid."""

    if since is None:
        return None

    if isinstance(since, datetime):
        since_dt = since
    else:
        try:
            since_dt = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
        except ValueError:
            return None

    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=timezone.utc)

    return since_dt


def format_duration(since: datetime | str | None) -> str | None:
    """Format the time elapsed since `since` as `Nd HH:MM` or `HH:MM`."""

    if (since_dt := parse_since(since)) is None:
        return None

    seconds = max(int((datetime.now(timezone.utc) - since_dt).total_seconds()), 0)

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours:02}:{minutes:02}"

    return f"{hours:02}:{minutes:02}"
