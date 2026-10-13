"""Where people are: at home, at a known place, or by street and town.

Positions come from Home Assistant person entities. A place is known either
because Home Assistant has a zone for it or because config.yaml lists it;
anywhere else is described by the address the phone itself worked out (the
companion app's "geocoded location" sensor), so no coordinates leave the
network to be looked up.
"""

from __future__ import annotations

import math

from .config import Config, Person, Place
from .ha import parse_time, to_float

UNKNOWN = {"unknown", "unavailable", None}
EARTH_RADIUS = 6_371_000  # metres


def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two positions (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(a))


def people_view(config: Config, live: dict) -> list[dict]:
    return [_person(person, config, live[person.instance or config.home.id].states) for person in config.people]


def watched(config: Config, instance_id: str) -> set[str]:
    """Person entities of an instance: a change of where someone is should show at once."""
    return {p.entity for p in config.people if (p.instance or config.home.id) == instance_id}


def _person(person: Person, config: Config, states: dict[str, dict]) -> dict:
    state = states.get(person.entity)
    attrs = (state or {}).get("attributes") or {}
    raw = (state or {}).get("state")
    latitude, longitude = to_float(attrs.get("latitude")), to_float(attrs.get("longitude"))
    located = latitude is not None and longitude is not None

    if raw == "home":
        kind, where = "home", "Home"
    elif raw not in UNKNOWN and raw != "not_home":
        kind, where = "place", raw  # a Home Assistant zone, by its name
    elif located and (place := _nearest(config.places, person.entity, latitude, longitude)):
        kind, where = "place", place.name
    elif located and (address := _address(person, attrs, states)):
        kind, where = "address", address
    elif located and (away := _from_home(states, latitude, longitude)):
        kind, where = "away", away
    elif raw == "not_home":
        kind, where = "away", "Away"
    else:
        kind, where = "unknown", "Unknown"

    return {
        "entity": person.entity,
        "name": person.name or attrs.get("friendly_name") or person.entity.split(".", 1)[1].replace("_", " ").title(),
        "kind": kind,
        "where": where,
        # When the position was last reported, not when the place last changed.
        "updated": parse_time(state.get("last_updated")) if state else None,
    }


def _nearest(places: list[Place], entity: str, latitude: float, longitude: float) -> Place | None:
    """The closest place the person is inside of, among those that are theirs."""
    inside = [
        (far, place) for place in places
        if (place.people is None or entity in place.people)
        and (far := distance(latitude, longitude, place.latitude, place.longitude)) <= place.radius
    ]
    return min(inside, key=lambda entry: entry[0])[1] if inside else None


def _address(person: Person, attrs: dict, states: dict[str, dict]) -> str | None:
    """Street and town, from the phone's own geocoding."""
    sensor = person.address
    if not sensor and str(attrs.get("source") or "").startswith("device_tracker."):
        sensor = f"sensor.{attrs['source'].split('.', 1)[1]}_geocoded_location"
    state = states.get(sensor) if sensor else None
    if not state or state.get("state") in UNKNOWN:
        return None
    # iOS and Android name the parts alike but do not agree on capitals.
    parts = {key.lower().replace("_", " "): value for key, value in (state.get("attributes") or {}).items()}
    pick = lambda *keys: next((str(parts[k]).strip() for k in keys if parts.get(k) not in (None, "", "N/A")), None)  # noqa: E731
    street, town = pick("thoroughfare", "name"), pick("locality", "sub locality", "sub administrative area")
    if street or town:
        return " · ".join(part for part in (street, town) if part)
    # No parts to pick from: the first lines of the full address will have to do.
    lines = [line.strip() for line in str(state["state"]).replace("\n", ",").split(",") if line.strip()]
    return " · ".join(lines[:2]) or None


def _from_home(states: dict[str, dict], latitude: float, longitude: float) -> str | None:
    """How far from home, when nothing better is known."""
    home = (states.get("zone.home") or {}).get("attributes") or {}
    lat, lon = to_float(home.get("latitude")), to_float(home.get("longitude"))
    if lat is None or lon is None:
        return None
    km = distance(latitude, longitude, lat, lon) / 1000
    return f"{km:.1f} km from home" if km < 10 else f"{km:,.0f} km from home"
