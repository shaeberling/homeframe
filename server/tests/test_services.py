import asyncio
from datetime import datetime, timedelta, timezone

from homeframe.config import Calendar, Todo
from homeframe.services import fetch_agenda, fetch_todos, starred

PREFIXES = Calendar().prefixes


def test_starred_strips_the_marker():
    assert starred("⭐ School concert", PREFIXES) == "School concert"
    assert starred("⭐️Grandma arrives", PREFIXES) == "Grandma arrives"
    assert starred("  ★ Recital ", PREFIXES) == "Recital"


def test_unstarred_and_empty_titles_are_dropped():
    assert starred("Dentist", PREFIXES) is None
    assert starred("Dinner ⭐", PREFIXES) is None
    assert starred("⭐", PREFIXES) is None
    assert starred(None, PREFIXES) is None


class Client:
    def __init__(self, events=(), items=()):
        self.events, self.items = list(events), list(items)

    async def calendar_events(self, entity_id, start, end):
        return self.events

    async def todo_items(self, entity_id):
        return self.items


def timed(title, start, hours=1):
    return {"summary": title, "start": {"dateTime": start.isoformat()}, "end": {"dateTime": (start + timedelta(hours=hours)).isoformat()}}


def all_day(title, day):
    return {"summary": title, "start": {"date": day.isoformat()}, "end": {"date": (day + timedelta(days=1)).isoformat()}}


def test_agenda_keeps_upcoming_starred_events_in_order():
    now = datetime.now(timezone.utc)
    client = Client([
        timed("⭐ Later", now + timedelta(days=2)),
        timed("Unstarred", now + timedelta(hours=1)),
        timed("⭐ Over", now - timedelta(hours=3)),
        timed("⭐ Running", now - timedelta(minutes=10)),
        all_day("⭐ Today", now.date()),
        timed("⭐ Soon", now + timedelta(hours=1)),
    ])
    agenda = asyncio.run(fetch_agenda(client, ["calendar.family"], Calendar(), "UTC"))
    titles = [e["title"] for e in agenda]
    # Today and Running both began in the past; which came first depends on the hour.
    assert sorted(titles[:2]) == ["Running", "Today"] and titles[2:] == ["Soon", "Later"]
    today = next(e for e in agenda if e["title"] == "Today")
    assert today["all_day"] and today["date"] == now.date().isoformat()


def test_agenda_respects_the_limit():
    now = datetime.now(timezone.utc)
    client = Client([timed(f"⭐ Event {n}", now + timedelta(hours=n)) for n in range(1, 6)])
    agenda = asyncio.run(fetch_agenda(client, ["calendar.family"], Calendar(limit=2), "UTC"))
    assert [e["title"] for e in agenda] == ["Event 1", "Event 2"]


def test_todos_put_dated_items_first():
    client = Client(items=[
        {"summary": "Whenever"},
        {"summary": "Friday", "due": "2026-10-16"},
        {"summary": " "},
        {"summary": "Tuesday", "due": "2026-10-13"},
    ])
    todos = asyncio.run(fetch_todos(client, ["todo.household"], Todo()))
    assert [t["title"] for t in todos] == ["Tuesday", "Friday", "Whenever"]
