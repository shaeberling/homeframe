"""The lights of a house, by floor and room.

Every light.* entity is shown unless excluded, plus whatever else the config
says is a lamp (often the switch it is plugged into). Rooms and floors are
Home Assistant's areas and floors.
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase

from .config import Instance
from .ha import parse_time, to_float

OFFLINE = {"unavailable", "unknown", None}


def light_entities(instance: Instance, states: dict[str, dict]) -> list[str]:
    lights = instance.lights
    if lights is None:
        return []
    found = [e for e in states if e.startswith("light.")]
    found += [e for pattern in lights.include for e in states if fnmatchcase(e, pattern) and e not in found]
    return [e for e in found if not any(fnmatchcase(e, pattern) for pattern in lights.exclude)]


def lights_view(instance: Instance, live) -> dict:
    floors: dict[tuple, dict[str, list]] = {}
    on = total = 0
    for entity_id in light_entities(instance, live.states):
        state = live.states[entity_id]
        attrs = state.get("attributes") or {}
        where = live.rooms.get(entity_id) or {}
        room = where.get("room")
        raw = state.get("state")
        status = "offline" if raw in OFFLINE else "on" if raw == "on" else "off"
        brightness = to_float(attrs.get("brightness"))
        name = attrs.get("friendly_name") or entity_id
        total += 1
        on += status == "on"
        floors.setdefault((where.get("floor"), where.get("level")), {}).setdefault(room, []).append({
            "entity": entity_id,
            "name": _short(name, room),
            "full_name": name,
            "status": status,
            # Home Assistant counts brightness to 255; only dimmable lights that are on have one.
            "brightness": round(brightness / 2.55) if brightness is not None and status == "on" else None,
            # What it is shining right now, for the lights that can tell. Home
            # Assistant gives white tones as RGB too.
            "color": _color(attrs.get("rgb_color")) if status == "on" else None,
            # When it was last switched (or went offline), not when it was last dimmed.
            "since": parse_time(state.get("last_changed")),
        })

    return {
        "key": f"lights-{instance.id}",
        "instance": instance.name,
        "stale": live.status == "error",
        "on": on,
        "total": total,
        "floors": [
            {
                "name": floor,
                "rooms": [
                    {"name": room, "lights": sorted(lights, key=lambda light: light["name"].lower())}
                    # Lights without a room come after the rooms.
                    for room, lights in sorted(rooms.items(), key=lambda entry: (entry[0] is None, (entry[0] or "").lower()))
                ],
            }
            for (floor, _level), rooms in sorted(floors.items(), key=_floor_order)
        ],
    }


def _color(raw) -> list[int] | None:
    try:
        red, green, blue = (min(255, max(0, int(channel))) for channel in raw)
    except (TypeError, ValueError):
        return None
    return [red, green, blue]


def _floor_order(entry) -> tuple:
    """Top floor first, as in a building; what has no floor comes last."""
    (name, level), _rooms = entry
    return name is None, -(level if level is not None else 0), (name or "").lower()


def _short(name: str, room: str | None) -> str:
    """The name without what the panel already says.

    Under "Kitchen", "Kitchen Shelves" is "Shelves"; in a list of lights,
    "Main Lights" is "Main". A name that would not survive is left alone.
    """
    short = name
    if room and short.lower().startswith(room.lower() + " "):
        rest = short[len(room):].strip()
        # "Garage 1 Light" would be left as "1 Light": some names need their room to make sense.
        if rest and not re.match(r"\d", rest):
            short = rest
    without = re.sub(r"\s+lights?$", "", short, flags=re.IGNORECASE)
    return without if without and not re.fullmatch(r"\d+", without) else short
