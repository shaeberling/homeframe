"""Keeps the latest state of every instance in memory and serves history."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .config import Config, Instance
from .dashboard import InstanceState, activity_item, build_dashboard, resolve_panels
from .demo import DemoClient
from .ha import HAClient, Series, describe_error
from .services import entities_of, fetch_agenda, fetch_todos
from .weather import days_from_daily, days_from_hourly, supports_daily, weather_entity

log = logging.getLogger("homeframe")

HISTORY_POINTS = 240
# Beyond this the recorder has usually purged raw history; use hourly statistics instead.
RAW_HISTORY_HOURS = 240
FORECAST_TTL = 30 * 60
FORECAST_RETRY = 5 * 60
REGISTRY_TTL = 30 * 60
REGISTRY_RETRY = 5 * 60
# How far back to ask for door/motion events; Home Assistant returns what it still has.
EVENT_DAYS = 30
EVENT_LIMIT = 100
AGENDA_TTL = 5 * 60
TODO_TTL = 5 * 60
SERVICE_RETRY = 60


class Hub:
    def __init__(self, config: Config):
        self.config = config
        client_type = DemoClient if config.demo else HAClient
        self._clients = {i.id: client_type(i) for i in config.instances}
        self._live = {i.id: InstanceState() for i in config.instances}
        self._tasks: list[asyncio.Task] = []
        self._history_cache: dict[int, tuple[float, dict, dict]] = {}
        self._history_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Last good answer of each service; None until it has answered once, or
        # when there is nothing to ask (no calendar or to-do list entities).
        self.agenda: list[dict] | None = None
        self.todos: list[dict] | None = None
        self._agenda_key: tuple | None = None
        self._agenda_at: float = 0
        self._todos_key: tuple | None = None
        self._todos_at: float = 0

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._poll(i)) for i in self.config.instances]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await asyncio.gather(*(c.close() for c in self._clients.values()))

    async def _poll(self, instance: Instance) -> None:
        live = self._live[instance.id]
        while True:
            try:
                states = await self._clients[instance.id].states()
                live.states = {s["entity_id"]: s for s in states}
                if live.error or not live.last_ok:
                    log.info("%s: connected, %d entities", instance.name, len(states))
                live.last_ok = time.time()
                live.error = None
            except Exception as error:  # keep polling whatever goes wrong
                message = describe_error(error, instance)
                if message != live.error:
                    log.warning("%s: %s", instance.name, message)
                live.error = message
            else:
                await self._refresh_time_zone(instance)
                await self._refresh_devices(instance)
                await self._refresh_forecast(instance)
                await self._refresh_agenda(instance)
                await self._refresh_todos(instance)
            await asyncio.sleep(self.config.poll_interval)

    @property
    def time_zone(self) -> str | None:
        """The zone the frame tells time in."""
        return self.config.frame.time_zone or self._live[self.config.home.id].time_zone

    def live(self, instance_id: str) -> InstanceState:
        return self._live[instance_id]

    async def _refresh_time_zone(self, instance: Instance) -> None:
        live = self._live[instance.id]
        if live.time_zone is not None:
            return
        try:
            live.time_zone = await self._clients[instance.id].time_zone()
        except Exception as error:  # asked again on the next poll
            log.warning("%s: reading the time zone failed: %s", instance.name, describe_error(error, instance))

    async def _refresh_agenda(self, instance: Instance) -> None:
        calendar = self.config.calendar
        if instance.id != (calendar.instance or self.config.home.id):
            return
        states = self._live[instance.id].states
        entities = entities_of(calendar.entities, states, "calendar.")
        if not entities:
            self.agenda = None
            return
        # A calendar entity changes state when an event starts or ends.
        key = tuple((e, (states.get(e) or {}).get("last_changed")) for e in entities)
        if key == self._agenda_key and time.time() - self._agenda_at < AGENDA_TTL:
            return
        try:
            self.agenda = await fetch_agenda(self._clients[instance.id], entities, calendar, self.time_zone)
            self._agenda_at = time.time()
        except Exception as error:  # keep showing the last good agenda
            log.warning("%s: reading the calendar failed: %s", instance.name, describe_error(error, instance))
            self._agenda_at = time.time() - AGENDA_TTL + SERVICE_RETRY
        self._agenda_key = key

    async def _refresh_todos(self, instance: Instance) -> None:
        todo = self.config.todo
        if instance.id != (todo.instance or self.config.home.id):
            return
        states = self._live[instance.id].states
        entities = entities_of(todo.entities, states, "todo.")
        if not entities:
            self.todos = None
            return
        # A to-do entity's state is its number of open items, so adding or
        # ticking one off shows up on the next poll rather than after the TTL.
        key = tuple((e, (states.get(e) or {}).get("state")) for e in entities)
        if key == self._todos_key and time.time() - self._todos_at < TODO_TTL:
            return
        try:
            self.todos = await fetch_todos(self._clients[instance.id], entities, todo)
            self._todos_at = time.time()
        except Exception as error:  # keep showing the last good list
            log.warning("%s: reading the to-do list failed: %s", instance.name, describe_error(error, instance))
            self._todos_at = time.time() - TODO_TTL + SERVICE_RETRY
        self._todos_key = key

    async def _refresh_devices(self, instance: Instance) -> None:
        live = self._live[instance.id]
        if time.time() - live.devices_at < REGISTRY_TTL:
            return
        try:
            live.devices = await self._clients[instance.id].entity_devices()
            live.devices_at = time.time()
        except Exception as error:  # without it entities are simply not grouped by device
            log.warning("%s: reading the device list failed: %s", instance.name, describe_error(error, instance))
            live.devices_at = time.time() - REGISTRY_TTL + REGISTRY_RETRY

    async def _refresh_forecast(self, instance: Instance) -> None:
        live = self._live[instance.id]
        entity = weather_entity(instance, live.states)
        if not entity:
            return
        if entity == live.forecast_entity and time.time() - live.forecast_at < FORECAST_TTL:
            return
        client = self._clients[instance.id]
        try:
            if live.time_zone is None:
                live.time_zone = await client.time_zone()
            days = days_from_daily(await client.forecast(entity, "daily")) if supports_daily(live.states[entity]) else []
            if not days:
                days = days_from_hourly(await client.forecast(entity, "hourly"), live.time_zone)
            live.forecast = days
            live.forecast_at = time.time()
        except Exception as error:  # the forecast is optional, never take the instance down with it
            log.warning("%s: forecast for %s failed: %s", instance.name, entity, describe_error(error, instance))
            live.forecast_at = time.time() - FORECAST_TTL + FORECAST_RETRY
        live.forecast_entity = entity

    def dashboard(self) -> dict:
        return build_dashboard(self.config, self._live)

    async def events(self, instance_id: str, entity_id: str) -> dict | None:
        """Recent state changes of a door or motion sensor, newest first."""
        instance = next((i for i in self.config.instances if i.id == instance_id), None)
        live = self._live.get(instance_id)
        item = activity_item(instance, live, entity_id) if instance else None
        if not item:
            return None  # only sensors that are on the dashboard can be queried

        client = self._clients[instance_id]
        end = datetime.now(timezone.utc)
        error = None
        try:
            changes = await client.state_changes(entity_id, end - timedelta(days=EVENT_DAYS), end)
            if live.time_zone is None:
                live.time_zone = await client.time_zone()
        except Exception as failure:
            changes, error = [], describe_error(failure, instance)

        # The current state is known even when its change is older than the recorded history.
        raw = (live.states.get(entity_id) or {}).get("state")
        if raw and item["since"] and (not changes or changes[-1][1] != raw):
            changes.append((item["since"], raw))

        events = []
        for index, (when, state) in enumerate(changes):
            previous = changes[index - 1] if index else None
            events.append({
                "time": when,
                "state": state,
                # how long the door was open / the motion lasted before this change
                "after": when - previous[0] if previous and previous[1] == "on" and state == "off" else None,
            })
        return {
            "entity": entity_id,
            "name": item["name"],
            "kind": item["kind"],
            "instance": instance.name,
            "time_zone": live.time_zone,
            "events": events[::-1][:EVENT_LIMIT],
            "error": error,
        }

    async def history(self, hours: int) -> dict:
        ttl = 60 if hours <= 24 else 300
        async with self._history_locks[hours]:
            wanted = self._displayed_entities()
            cached = self._history_cache.get(hours)
            # Auto-discovered panels fill in after startup, so the cache is
            # only good for the set of sensors it was fetched for.
            if cached and cached[1] == wanted and time.time() - cached[0] < ttl:
                return cached[2]
            payload = await self._fetch_history(hours, wanted)
            # Don't pin a failed fetch for the whole TTL.
            if not payload["errors"]:
                self._history_cache[hours] = (time.time(), wanted, payload)
            return payload

    def _displayed_entities(self) -> dict[str, list[str]]:
        wanted: dict[str, list[str]] = {}
        for _key, panel in resolve_panels(self.config, self._live):
            entities = wanted.setdefault(panel.instance, [])
            entities.extend(s.entity for s in panel.sensors if s.entity not in entities)
        return wanted

    async def _fetch_history(self, hours: int, wanted: dict[str, list[str]]) -> dict:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)

        instance_ids = list(wanted)
        results = await asyncio.gather(
            *(
                self._clients[i].history(wanted[i], start, end) if hours <= RAW_HISTORY_HOURS
                else self._clients[i].statistics(wanted[i], start, end)
                for i in instance_ids
            ),
            return_exceptions=True,
        )

        series: dict[str, list] = {}
        errors: dict[str, str] = {}
        for instance_id, result in zip(instance_ids, results):
            if isinstance(result, Exception):
                errors[instance_id] = describe_error(result, self.config.instance(instance_id))
                continue
            for entity_id, points in result.items():
                series[f"{instance_id}:{entity_id}"] = downsample(points, start.timestamp(), end.timestamp())

        return {
            "hours": hours,
            "start": int(start.timestamp() * 1000),
            "end": int(end.timestamp() * 1000),
            "series": series,
            "errors": errors,
        }


def downsample(points: Series, start: float, end: float, buckets: int = HISTORY_POINTS) -> list[list]:
    """Average readings into at most `buckets` evenly spaced [ms, value] points.

    A bucket holding only unusable readings becomes [ms, null] so the chart
    shows a gap; buckets without any reading are skipped, because Home
    Assistant only records changes and the last value still holds.
    """
    width = (end - start) / buckets
    sums = [0.0] * buckets
    counts = [0] * buckets
    gaps = [False] * buckets
    last: float | None = None
    for when, value in points:
        index = min(buckets - 1, max(0, int((when - start) / width)))
        if value is None:
            gaps[index] = True
        else:
            sums[index] += value
            counts[index] += 1
        last = value

    out: list[list] = []
    for index in range(buckets):
        when = int((start + (index + 0.5) * width) * 1000)
        if counts[index]:
            out.append([when, round(sums[index] / counts[index], 2)])
        elif gaps[index]:
            out.append([when, None])
    # Carry the last reading to the right edge so slow sensors don't end early.
    if last is not None and out:
        out.append([int(end * 1000), out[-1][1] if out[-1][1] is not None else round(last, 2)])
    return out
