"""Synthetic instances for `--demo`, so both displays can be tried without Home Assistant."""

from __future__ import annotations

import math
import time
import zlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import ActivityItem, Config, Instance, Panel, Sensor
from .ha import Series

HOUR = 3600.0

# (entity, friendly name, base temperature, daily swing, behaviour)
TEMPERATURES = {
    "home": [
        ("sensor.living_room_temperature", "Living room", 21.6, 0.9, None),
        ("sensor.kitchen_temperature", "Kitchen", 20.9, 1.2, None),
        ("sensor.office_temperature", "Office", 21.2, 0.8, None),
        ("sensor.basement_temperature", "Basement", 14.9, 0.4, None),
        ("sensor.bedroom_temperature", "Bedroom", 18.7, 0.7, None),
        ("sensor.bathroom_temperature", "Bathroom", 23.1, 1.0, None),
        ("sensor.nursery_temperature", "Nursery", 20.3, 0.6, None),
    ],
    "cabin": [
        ("sensor.main_room_temperature", "Main room", 18.4, 1.1, None),
        ("sensor.cabin_bedroom_temperature", "Bedroom", 17.2, 0.8, None),
        ("sensor.loft_temperature", "Loft", 17.9, 1.3, None),
        ("sensor.pump_house_temperature", "Pump house", 17.0, 0.5, "heating_failed"),
        ("sensor.workshop_temperature", "Workshop", 16.8, 0.9, "offline"),
    ],
}

BATTERIES = {
    "home": [
        ("sensor.front_door_battery", "Front door sensor battery", 12),
        ("sensor.living_room_battery", "Living room sensor battery", 87),
        ("sensor.basement_battery", "Basement sensor battery", 55),
    ],
    "cabin": [
        ("sensor.loft_battery", "Loft sensor battery", 9),
        ("sensor.pump_house_battery", "Pump house sensor battery", 64),
        ("sensor.main_room_battery", "Main room sensor battery", 91),
        ("sensor.cabin_door_battery", "Door sensor battery", 38),
    ],
}

# (time zone, current condition, current temperature, forecast as (condition, high, low, mm))
WEATHER = {
    "home": ("Europe/Berlin", "partlycloudy", 11.4, [
        ("partlycloudy", 13, 6, 0), ("rainy", 11, 7, 4.2), ("pouring", 9, 5, 11.6),
        ("cloudy", 10, 4, 0.3), ("sunny", 12, 2, 0), ("fog", 8, 1, 0),
    ]),
    "cabin": ("Europe/Oslo", "snowy", -2.3, [
        ("snowy", -1, -7, 3.1), ("snowy-rainy", 1, -3, 2.0), ("cloudy", 0, -5, 0),
        ("sunny", -2, -11, 0), ("windy", 2, -4, 0), ("lightning-rainy", 4, 0, 6.5),
    ]),
}

# (entity, friendly name, device class, state, hours since the last change)
ACTIVITY = {
    "home": [
        ("binary_sensor.front_door", "Front door", "door", "off", 1.6),
        ("binary_sensor.garage_door", "Garage door", "garage_door", "on", 0.3),
        ("binary_sensor.hall_motion", "Hall motion", "motion", "off", 0.1),
    ],
    "cabin": [
        ("binary_sensor.cabin_front_door", "Front door", "door", "off", 26.5),
        ("binary_sensor.cabin_shed_door", "Shed door", "door", "on", 0.4),
        ("binary_sensor.cabin_hall_motion", "Hall motion", "motion", "off", 71.0),
        ("binary_sensor.cabin_loft_window", "Loft window", "window", "unavailable", 3.2),
    ],
}

# (title, days from today, start hour or None for all day); only starred ones reach the frame
EVENTS = [
    ("⭐ School concert", 0, 18.5),
    ("Dentist", 0, 13.5),
    ("⭐️ Grandma arrives", 1, None),
    ("⭐ Football final", 2, 10),
    ("Standup", 1, 9),
    ("⭐ Cabin weekend", 5, None),
]

TODOS = ["Bins out tonight", "Order more coffee", "Book the chimney sweep", "Return library books"]

FAILED_FOR = 9 * HOUR
OFFLINE_FOR = 3.2 * HOUR


def demo_config() -> Config:
    def panel(title, instance, names):
        entities = {name: entity for entity, name, *_ in TEMPERATURES[instance]}
        return Panel(title=title, instance=instance, sensors=[Sensor(entity=entities[n]) for n in names])

    return Config(
        instances=[
            Instance(
                id="home", name="Home", url="demo://home", token="demo",
                activity=[ActivityItem(entity) for entity, *_ in ACTIVITY["home"]],
            ),
            Instance(
                id="cabin", name="Cabin", url="demo://cabin", token="demo",
                batteries=[entity for entity, *_ in BATTERIES["cabin"]],
                activity=[ActivityItem(entity) for entity, *_ in ACTIVITY["cabin"]],
            ),
        ],
        panels=[
            panel("Ground floor", "home", ["Living room", "Kitchen", "Office", "Basement"]),
            panel("Upper floor", "home", ["Bedroom", "Bathroom", "Nursery"]),
            panel("Cabin", "cabin", ["Main room", "Bedroom", "Loft", "Pump house", "Workshop"]),
        ],
        poll_interval=5,
        demo=True,
    )


def _iso(when: float) -> str:
    return datetime.fromtimestamp(when, timezone.utc).isoformat()


class DemoClient:
    def __init__(self, instance: Instance):
        self.instance = instance
        self._started = time.time()

    async def close(self) -> None:
        pass

    async def time_zone(self) -> str:
        return WEATHER[self.instance.id][0]

    async def forecast(self, entity_id: str, kind: str) -> list[dict]:
        noon = datetime.now(timezone.utc).replace(hour=11, minute=0, second=0, microsecond=0).timestamp()
        return [
            {"datetime": _iso(noon + day * 24 * HOUR), "condition": condition, "temperature": high, "templow": low, "precipitation": rain}
            for day, (condition, high, low, rain) in enumerate(WEATHER[self.instance.id][3])
        ]

    async def calendar_events(self, entity_id: str, start: datetime, end: datetime) -> list[dict]:
        zone = ZoneInfo(WEATHER[self.instance.id][0])
        today = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        events = []
        for title, days, hour in EVENTS:
            day = today + timedelta(days=days)
            if hour is None:
                span = {"start": {"date": day.date().isoformat()}, "end": {"date": (day + timedelta(days=1)).date().isoformat()}}
            else:
                begins = day + timedelta(hours=hour)
                span = {"start": {"dateTime": begins.isoformat()}, "end": {"dateTime": (begins + timedelta(hours=1)).isoformat()}}
            events.append({"summary": title, **span})
        return events

    async def todo_items(self, entity_id: str) -> list[dict]:
        return [{"summary": title, "status": "needs_action"} for title in TODOS]

    def _value(self, entity: str, base: float, swing: float, behaviour: str | None, when: float) -> float | None:
        seed = zlib.crc32(entity.encode()) % 1000 / 1000 * math.tau
        hours = when / HOUR
        value = (
            base
            + swing * math.sin((hours - 9) / 24 * math.tau + seed / 6)
            + 0.18 * math.sin(hours * 1.9 + seed)
            + 0.08 * math.sin(hours * 7.3 + seed * 3)
        )
        if behaviour == "offline" and when > self._started - OFFLINE_FOR:
            return None
        if behaviour == "heating_failed":
            failed_at = self._started - FAILED_FOR
            if when > failed_at:
                outside = 3.0
                value = outside + (value - outside) * math.exp(-(when - failed_at) / (6 * HOUR))
        return value

    async def states(self) -> list[dict]:
        now = time.time()
        states = []
        for entity, name, base, swing, behaviour in TEMPERATURES[self.instance.id]:
            value = self._value(entity, base, swing, behaviour, now)
            changed = now if value is not None else self._started - OFFLINE_FOR
            states.append({
                "entity_id": entity,
                "state": "unavailable" if value is None else f"{value:.1f}",
                "attributes": {
                    "friendly_name": f"{name} temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
                "last_changed": _iso(changed),
                "last_updated": _iso(changed),
            })
        for entity, name, device_class, value, hours_ago in ACTIVITY[self.instance.id]:
            changed = _iso(self._started - hours_ago * HOUR)
            states.append({
                "entity_id": entity,
                "state": value,
                "attributes": {"friendly_name": name, "device_class": device_class},
                "last_changed": changed,
                "last_updated": changed,
            })
        if self.instance.id == "home":
            started = _iso(self._started)
            states.append({
                "entity_id": "calendar.family", "state": "off",
                "attributes": {"friendly_name": "Family"}, "last_changed": started, "last_updated": started,
            })
            states.append({
                "entity_id": "todo.household", "state": str(len(TODOS)),
                "attributes": {"friendly_name": "Household"}, "last_changed": started, "last_updated": started,
            })
        _zone, condition, temperature, _days = WEATHER[self.instance.id]
        states.append({
            "entity_id": "weather.forecast_home",
            "state": condition,
            "attributes": {
                "friendly_name": "Forecast Home",
                "temperature": temperature,
                "temperature_unit": "°C",
                "humidity": 71,
                "wind_speed": 14.8,
                "wind_speed_unit": "km/h",
                "precipitation_unit": "mm",
                "supported_features": 3,
            },
            "last_changed": _iso(now),
            "last_updated": _iso(now),
        })
        for entity, name, level in BATTERIES[self.instance.id]:
            states.append({
                "entity_id": entity,
                "state": str(level),
                "attributes": {
                    "friendly_name": name,
                    "device_class": "battery",
                    "unit_of_measurement": "%",
                },
                "last_changed": _iso(now - 6 * HOUR),
                "last_updated": _iso(now - 6 * HOUR),
            })
        return states

    async def state_changes(self, entity_id: str, start: datetime, end: datetime) -> list[tuple[float, str]]:
        hours_ago = next(hours for entity, *_rest, hours in ACTIVITY[self.instance.id] if entity == entity_id)
        last = self._started - hours_ago * HOUR
        # A handful of earlier open/close pairs leading up to the current state.
        changes = []
        for n in range(4, 0, -1):
            opened = last - n * 19.3 * HOUR
            changes += [(opened, "on"), (opened + 140 * n, "off")]
        return [c for c in changes if c[0] >= start.timestamp()]

    async def entity_devices(self) -> dict[str, str]:
        # A sensor's temperature and battery entities belong to one device.
        entities = [e for e, *_ in TEMPERATURES[self.instance.id]] + [e for e, *_ in BATTERIES[self.instance.id]]
        return {e: e.split(".", 1)[1].removesuffix("_temperature").removesuffix("_battery") for e in entities}

    async def statistics(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        return await self.history(entity_ids, start, end)

    async def history(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        t0, t1 = start.timestamp(), end.timestamp()
        step = max(300.0, (t1 - t0) / 600)
        specs = {entity: spec for entity, *spec in TEMPERATURES[self.instance.id]}
        result: dict[str, Series] = {}
        for entity in entity_ids:
            if entity not in specs:
                continue
            _name, base, swing, behaviour = specs[entity]
            series: Series = []
            when = t0
            while when <= t1:
                series.append((when, self._value(entity, base, swing, behaviour, when)))
                when += step
            result[entity] = series
        return result
