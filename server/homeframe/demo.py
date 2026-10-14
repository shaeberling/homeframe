"""Synthetic instances for `--demo`, so both displays can be tried without Home Assistant.

Two made-up houses at the scale of a real setup: a family home with a full
set of lights, doors and sensors, and a second house far away that mostly
stands empty.
"""

from __future__ import annotations

import math
import time
import zlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import ActivityItem, Attention, Config, Instance, Lights, Panel, Person, Place, Sensor
from .ha import Series

HOUR = 3600.0

# (entity, friendly name, base temperature, daily swing, behaviour)
TEMPERATURES = {
    "home": [
        ("sensor.main_bathroom_temperature", "Main bathroom", 22.4, 1.4, None),
        ("sensor.bedroom_temperature", "Bedroom", 19.1, 0.7, None),
        ("sensor.kids_room_temperature", "Kids' room", 20.3, 0.6, None),
        ("sensor.kitchen_temperature", "Kitchen", 20.9, 1.2, None),
        ("sensor.workshop_temperature", "Workshop", 18.2, 0.9, None),
        ("sensor.garage_temperature", "Garage", 14.6, 1.6, None),
    ],
    "cabin": [
        ("sensor.upstairs_bath_temperature", "Upstairs bath", 17.6, 0.8, None),
        ("sensor.landing_temperature", "Landing", 16.4, 0.7, None),
        ("sensor.studio_temperature", "Studio", 15.8, 1.0, None),
        ("sensor.downstairs_bath_temperature", "Downstairs bath", 17.1, 0.6, None),
        ("sensor.cabin_bedroom_temperature", "Bedroom", 16.2, 0.8, None),
        ("sensor.cabin_kitchen_temperature", "Kitchen", 17.4, 1.1, None),
        ("sensor.dining_room_temperature", "Dining room", 16.9, 0.9, None),
        ("sensor.reading_nook_temperature", "Reading nook", 16.5, 0.8, None),
        ("sensor.main_room_temperature", "Main room", 18.4, 1.1, None),
        ("sensor.pump_house_temperature", "Pump house", 17.0, 0.5, "heating_failed"),
        ("sensor.boathouse_temperature", "Boathouse", 13.8, 1.2, "offline"),
        ("sensor.mudroom_temperature", "Mudroom", 12.9, 1.5, None),
    ],
}

# Sensors that also measure humidity: (temperature entity, humidity entity, base %)
HUMIDITY = {
    "home": [
        ("sensor.main_bathroom_temperature", "sensor.main_bathroom_humidity", 63),
        ("sensor.bedroom_temperature", "sensor.bedroom_humidity", 48),
        ("sensor.kids_room_temperature", "sensor.kids_room_humidity", 51),
        ("sensor.workshop_temperature", "sensor.workshop_humidity", 44),
        ("sensor.garage_temperature", "sensor.garage_humidity", 67),
    ],
    "cabin": [
        ("sensor.studio_temperature", "sensor.studio_humidity", 53),
        ("sensor.main_room_temperature", "sensor.main_room_humidity", 50),
        ("sensor.mudroom_temperature", "sensor.mudroom_humidity", 61),
    ],
}

# (entity, friendly name, level in %, or "on"/"off" for a sensor that only says low)
BATTERIES = {
    "home": [
        ("sensor.front_door_battery", "Front door sensor battery", 12),
        ("sensor.back_door_battery", "Back door sensor battery", 78),
        ("sensor.patio_door_battery", "Patio door sensor battery", 64),
        ("sensor.hallway_motion_battery", "Hallway motion battery", 41),
        ("sensor.basement_motion_battery", "Basement motion battery", 93),
        ("sensor.bedroom_sensor_battery", "Bedroom sensor battery", 87),
        ("sensor.kids_room_sensor_battery", "Kids' room sensor battery", 55),
        ("sensor.workshop_sensor_battery", "Workshop sensor battery", 70),
        ("sensor.garage_sensor_battery", "Garage sensor battery", 33),
        ("sensor.remote_battery", "Remote battery", 100),
        ("sensor.smoke_alarm_battery", "Smoke alarm battery", 96),
        ("binary_sensor.door_lock_battery", "Door lock battery", "off"),
    ],
    "cabin": [
        ("sensor.cabin_front_door_battery", "Front door sensor battery", 9),
        ("sensor.pump_house_battery", "Pump house sensor battery", 64),
        ("sensor.main_room_battery", "Main room sensor battery", 91),
        ("sensor.terrace_door_battery", "Terrace door sensor battery", 38),
        ("sensor.laundry_door_battery", "Laundry door sensor battery", 82),
        ("sensor.studio_battery", "Studio sensor battery", 74),
    ],
}

# (time zone, current condition, current temperature, forecast as (condition, high, low, mm))
WEATHER = {
    "home": ("America/New_York", "partlycloudy", 11.4, [
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
        ("binary_sensor.front_door", "Front door", "door", "off", 0.4),
        ("binary_sensor.hallway_motion", "Hallway", "motion", "on", 0.0),
        ("binary_sensor.back_door", "Back door", "door", "off", 2.7),
        ("cover.garage_left", "Garage left", "garage", "open", 0.2),
        ("binary_sensor.living_room_motion", "Living room", "motion", "off", 0.9),
        ("binary_sensor.stairs_motion", "Stairs", "motion", "off", 5.5),
        ("cover.garage_right", "Garage right", "garage", "closed", 19.8),
        ("binary_sensor.patio_door", "Patio door", "door", "off", 31.0),
        ("binary_sensor.basement_motion", "Basement", "motion", "off", 52.0),
        ("binary_sensor.guest_room_door", "Guest room door", "door", "off", 140.0),
        ("binary_sensor.bathroom_door", "Bathroom door", "door", "off", 410.0),
    ],
    "cabin": [
        ("binary_sensor.laundry_door", "Laundry door", "door", "on", 0.4),
        ("binary_sensor.cabin_front_door", "Front door", "door", "off", 26.5),
        ("binary_sensor.terrace_door", "Terrace door", "door", "off", 47.2),
        ("binary_sensor.cabin_garage_door", "Garage door", "door", "off", 47.3),
        ("cover.studio_shade", "Studio shade", "shade", "closed", 14.0),
        ("cover.bedroom_shade", "Bedroom shade", "shade", "open", 3.0),
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
    ("⭐ Lakeside weekend", 5, None),
]

UP, GROUND, BASEMENT = ("Upper floor", 1), ("Ground floor", 0), ("Basement", -1)

# (entity, friendly name, room, (floor, level) or None, state, brightness of 255 or None, colour or None)
LIGHTS = {
    "home": [
        ("light.bedroom_ceiling", "Bedroom Ceiling", "Bedroom", UP, "off", None, None),
        ("light.bedroom_left_nightstand", "Bedroom Left nightstand", "Bedroom", UP, "on", 70, None),
        ("light.bedroom_right_nightstand", "Bedroom Right nightstand", "Bedroom", UP, "off", None, None),
        ("light.main_bathroom_mirror", "Main bathroom Mirror", "Main bathroom", UP, "off", None, None),
        ("light.kids_room_ceiling", "Kids' room Ceiling", "Kids' room", UP, "off", None, None),
        ("light.kids_room_night_light", "Kids' room Night light", "Kids' room", UP, "on", 26, (255, 120, 200)),
        ("light.landing", "Landing", "Landing", UP, "unavailable", None, None),
        ("light.kitchen_ceiling", "Kitchen Ceiling", "Kitchen", GROUND, "on", None, None),
        ("light.kitchen_counter", "Kitchen Counter", "Kitchen", GROUND, "on", 140, None),
        ("light.kitchen_island", "Kitchen Island", "Kitchen", GROUND, "off", None, None),
        ("light.dining_room_pendant", "Dining room Pendant", "Dining room", GROUND, "on", 102, None),
        ("light.living_room_ceiling", "Living room Ceiling", "Living room", GROUND, "off", None, None),
        ("light.living_room_floor_lamp", "Living room Floor lamp", "Living room", GROUND, "on", 128, None),
        ("light.living_room_corner", "Living room Corner", "Living room", GROUND, "on", 204, (90, 140, 255)),
        ("light.living_room_tv_backlight", "Living room TV backlight", "Living room", GROUND, "on", 255, (170, 80, 255)),
        ("light.hall", "Hall", "Hall", GROUND, "off", None, None),
        ("light.staircase", "Staircase", "Hall", GROUND, "on", 102, None),
        ("light.workshop_ceiling", "Workshop Ceiling", "Workshop", BASEMENT, "on", None, None),
        ("light.workshop_bench", "Workshop Bench", "Workshop", BASEMENT, "on", 230, None),
        ("light.laundry", "Laundry", "Laundry", BASEMENT, "off", None, None),
        ("light.porch", "Porch", "Outside", None, "on", 180, (255, 170, 80)),
        ("light.backyard", "Backyard", "Outside", None, "off", None, None),
    ],
    "cabin": [
        ("switch.cabin_floor_lamp", "Floor lamp", "Main room", None, "off", None, None),
        ("switch.cabin_reading_lamp", "Reading lamp", "Reading nook", None, "on", None, None),
        ("switch.cabin_porch_lamp", "Porch lamp", None, None, "on", None, None),
    ],
}

TODOS = ["Bins out tonight", "Order more coffee", "Book the chimney sweep", "Return library books"]

FAILED_FOR = 9 * HOUR
OFFLINE_FOR = 3.2 * HOUR

HOME_AT = (40.6782, -73.9442)


def demo_config() -> Config:
    def panel(instance):
        humidity = {entity: humid for entity, humid, _ in HUMIDITY[instance]}
        sensors = []
        for entity, *_ in TEMPERATURES[instance]:
            sensor = Sensor(entity=entity)
            if entity == "sensor.kitchen_temperature":
                sensor.climate = "climate.downstairs"
            # Humidity on the card for some; the detail chart finds the others itself.
            if instance == "cabin" and entity in humidity:
                sensor.humidity = humidity[entity]
            sensors.append(sensor)
        return Panel(title="Temperatures", instance=instance, sensors=sensors)

    return Config(
        instances=[
            Instance(
                id="home", name="Hillcrest", url="demo://home", token="demo",
                activity=[ActivityItem(entity) for entity, *_ in ACTIVITY["home"]],
                lights=Lights(),
                all_batteries=True,
            ),
            Instance(
                id="cabin", name="Lakeside", url="demo://cabin", token="demo",
                batteries=[entity for entity, *_ in BATTERIES["cabin"]],
                activity=[ActivityItem(entity) for entity, *_ in ACTIVITY["cabin"]],
                lights=Lights(include=["switch.cabin_*_lamp"]),
            ),
        ],
        panels=[panel("home"), panel("cabin")],
        people=[Person("person.alex", "home"), Person("person.sam", "home")],
        places=[
            Place("Office", 40.7536, -73.9832, 150, people=["person.alex"]),
            Place("Gym", 40.6729, -73.9708, 120),
        ],
        attention=Attention(temperature_low=12, temperature_critical=8),
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

    def _humidity(self, temperature: str, base: float, when: float) -> float | None:
        _name, warm, swing, behaviour = next(spec for entity, *spec in TEMPERATURES[self.instance.id] if entity == temperature)
        reading = self._value(temperature, warm, swing, behaviour, when)
        if reading is None:
            return None
        # Drier as it warms up, and a shower in the bathroom every morning.
        value = base - 2.5 * (reading - warm) + 1.5 * math.sin(when / HOUR * 0.7)
        if "bathroom" in temperature:
            value += 22 * math.exp(-(((when / HOUR) % 24 - 11.5) ** 2) / 0.3)
        return min(99.0, value)

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
        for temperature, entity, base in HUMIDITY[self.instance.id]:
            value = self._humidity(temperature, base, now)
            states.append({
                "entity_id": entity,
                "state": "unavailable" if value is None else f"{value:.1f}",
                "attributes": {"friendly_name": "Humidity", "device_class": "humidity", "unit_of_measurement": "%"},
                "last_changed": _iso(now),
                "last_updated": _iso(now),
            })
        for entity, name, device_class, value, hours_ago in ACTIVITY[self.instance.id]:
            # Motion that is on right now was only just set off.
            active = value == "on" and device_class == "motion"
            changed = _iso(now - 20 if active else self._started - hours_ago * HOUR)
            states.append({
                "entity_id": entity,
                "state": value,
                "attributes": {"friendly_name": name, "device_class": device_class},
                "last_changed": changed,
                "last_updated": changed,
            })
        for n, (entity, name, _room, _floor, value, brightness, colour) in enumerate(LIGHTS[self.instance.id]):
            changed = _iso(self._started - (n * 37 % 300) * 60)
            attrs = {"friendly_name": name}
            if brightness:
                attrs["brightness"] = brightness
            if colour:
                attrs["rgb_color"] = list(colour)
            states.append({"entity_id": entity, "state": value, "attributes": attrs, "last_changed": changed, "last_updated": changed})
        if self.instance.id == "home":
            states += self._people(now)
            started = _iso(self._started)
            states.append({
                "entity_id": "climate.downstairs", "state": "heat",
                "attributes": {"friendly_name": "Downstairs", "temperature": 20.5},
                "last_changed": started, "last_updated": started,
            })
            states.append({
                "entity_id": "calendar.family", "state": "off",
                "attributes": {"friendly_name": "Family"}, "last_changed": started, "last_updated": started,
            })
            states.append({
                "entity_id": "todo.household", "state": str(len(TODOS)),
                "attributes": {"friendly_name": "Household"}, "last_changed": started, "last_updated": started,
            })
        zone, condition, temperature, _days = WEATHER[self.instance.id]
        tomorrow = datetime.now(ZoneInfo(zone)).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        states.append({
            "entity_id": "sun.sun", "state": "above_horizon",
            "attributes": {
                "next_rising": (tomorrow + timedelta(hours=7.2)).isoformat(),
                "next_setting": (tomorrow + timedelta(hours=18.1)).isoformat(),
            },
            "last_changed": _iso(now), "last_updated": _iso(now),
        })
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
                    **({"unit_of_measurement": "%"} if isinstance(level, int) else {}),
                },
                "last_changed": _iso(now - 6 * HOUR),
                "last_updated": _iso(now - 6 * HOUR),
            })
        return states

    def _people(self, now: float) -> list[dict]:
        def entity(entity_id, state, attrs, minutes_ago):
            when = _iso(now - minutes_ago * 60)
            return {"entity_id": entity_id, "state": state, "attributes": attrs, "last_changed": when, "last_updated": when}

        home = {"latitude": HOME_AT[0], "longitude": HOME_AT[1]}
        return [
            entity("zone.home", "1", {"friendly_name": "Home", **home, "radius": 100}, 600),
            # Inside the circle of a place from the config.
            entity("person.alex", "not_home", {"friendly_name": "Alex", "latitude": 40.7538, "longitude": -73.9830, "source": "device_tracker.alex_phone"}, 6),
            entity("person.sam", "home", {"friendly_name": "Sam", **home, "source": "device_tracker.sam_phone"}, 38),
        ]

    async def state_changes(self, entity_id: str, start: datetime, end: datetime) -> list[tuple[float, str]]:
        hours_ago = next(hours for entity, *_rest, hours in ACTIVITY[self.instance.id] if entity == entity_id)
        last = self._started - hours_ago * HOUR
        on, off = ("open", "closed") if entity_id.startswith("cover.") else ("on", "off")
        # A handful of earlier open/close pairs leading up to the current state.
        changes = []
        for n in range(4, 0, -1):
            opened = last - n * 19.3 * HOUR
            changes += [(opened, on), (opened + 140 * n, off)]
        return [c for c in changes if c[0] >= start.timestamp()]

    async def entity_devices(self) -> dict[str, str]:
        # A sensor's temperature, humidity and battery entities belong to one device.
        devices = {e: e.split(".", 1)[1].removesuffix("_temperature") for e, *_ in TEMPERATURES[self.instance.id]}
        devices |= {e: e.split(".", 1)[1].removesuffix("_battery") for e, *_ in BATTERIES[self.instance.id]}
        devices |= {humidity: devices[temperature] for temperature, humidity, _ in HUMIDITY[self.instance.id]}
        return devices

    async def entity_rooms(self) -> dict[str, dict]:
        return {
            entity: {"room": room, "floor": floor[0] if floor else None, "level": floor[1] if floor else None}
            for entity, _name, room, floor, *_ in LIGHTS[self.instance.id] if room
        }

    async def statistics(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        return await self.history(entity_ids, start, end)

    async def history(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        t0, t1 = start.timestamp(), end.timestamp()
        step = max(300.0, (t1 - t0) / 600)
        specs = {entity: spec for entity, *spec in TEMPERATURES[self.instance.id]}
        humidity = {humid: (temperature, base) for temperature, humid, base in HUMIDITY[self.instance.id]}
        result: dict[str, Series] = {}
        for entity in entity_ids:
            if entity in humidity:
                read = lambda when, entity=entity: self._humidity(*humidity[entity], when)  # noqa: E731
            elif entity in specs:
                read = lambda when, entity=entity: self._value(entity, *specs[entity][1:], when)  # noqa: E731
            else:
                continue
            series: Series = []
            when = t0
            while when <= t1:
                series.append((when, read(when)))
                when += step
            result[entity] = series
        return result
