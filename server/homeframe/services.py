"""Family data that comes from services rather than sensors: the agenda and the to-do list.

Both are read through Home Assistant today (a Google calendar connected there
shows up as a calendar.* entity), but the hub only relies on the two fetch
functions below, so a direct connector can replace either without touching
the views.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Calendar, Todo

# Emoji are often followed by a variation selector that is not part of the title.
VARIATION_SELECTOR = "\ufe0f"


def entities_of(configured: list[str] | None, states: dict[str, dict], domain: str) -> list[str]:
    """The configured entities, or every entity of the domain when none are listed."""
    if configured is not None:
        return configured
    return sorted(e for e in states if e.startswith(domain))


def zone_of(time_zone: str | None):
    try:
        return ZoneInfo(time_zone) if time_zone else timezone.utc
    except ZoneInfoNotFoundError:
        return timezone.utc


def starred(summary: str | None, prefixes: list[str]) -> str | None:
    """The title without its marker if it starts with one, otherwise None."""
    text = (summary or "").strip()
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):].lstrip(VARIATION_SELECTOR).strip() or None
    return None


def _moment(raw: dict | None, zone) -> tuple[datetime, bool] | None:
    """A calendar start or end as (aware datetime, is all-day)."""
    raw = raw or {}
    try:
        if raw.get("dateTime"):
            when = datetime.fromisoformat(raw["dateTime"])
            return (when if when.tzinfo else when.replace(tzinfo=zone)), False
        if raw.get("date"):
            return datetime.combine(date.fromisoformat(raw["date"]), time.min, zone), True
    except ValueError:
        pass
    return None


async def fetch_agenda(client, entities: list[str], calendar: Calendar, time_zone: str | None) -> list[dict]:
    """Upcoming starred events of the given calendars, soonest first."""
    zone = zone_of(time_zone)
    now = datetime.now(zone)
    # From midnight, so an all-day event of today is still inside the window.
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=calendar.days)

    events = []
    for entity in entities:
        for raw in await client.calendar_events(entity, start, end):
            title = starred(raw.get("summary"), calendar.prefixes)
            begins = _moment(raw.get("start"), zone)
            finishes = _moment(raw.get("end"), zone)
            if not title or not begins:
                continue
            if (finishes[0] if finishes else begins[0]) <= now:
                continue  # already over
            events.append({
                "title": title,
                "start": int(begins[0].timestamp() * 1000),
                "all_day": begins[1],
                # All-day events are dates, not instants: the page must not shift them by zone.
                "date": begins[0].date().isoformat(),
            })
    events.sort(key=lambda e: (e["start"], not e["all_day"], e["title"].lower()))
    return events[: calendar.limit]


async def fetch_todos(client, entities: list[str], todo: Todo) -> list[dict]:
    """Open to-do items of the given lists, those with a due date first."""
    items = []
    for entity in entities:
        for raw in await client.todo_items(entity):
            title = (raw.get("summary") or "").strip()
            if title:
                items.append({"title": title, "due": raw.get("due")})
    # A stable sort: undated items keep the order of their list.
    items.sort(key=lambda i: (i["due"] is None, i["due"] or ""))
    return items[: todo.limit]
