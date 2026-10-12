"""Weather: picking an instance's weather entity and shaping its forecast for the UI."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Instance
from .ha import parse_time, to_float

FORECAST_DAYS = 6
# WeatherEntityFeature.FORECAST_DAILY in Home Assistant.
SUPPORTS_DAILY = 1
UNAVAILABLE = {"unavailable", "unknown"}


def weather_entity(instance: Instance, states: dict[str, dict]) -> str | None:
    if instance.weather is False:
        return None
    if isinstance(instance.weather, str):
        return instance.weather if instance.weather in states else None
    candidates = sorted(e for e in states if e.startswith("weather."))
    available = [e for e in candidates if states[e].get("state") not in UNAVAILABLE]
    return next(iter(available or candidates), None)


def supports_daily(state: dict) -> bool:
    features = (state.get("attributes") or {}).get("supported_features")
    # Without the attribute, just try daily first.
    return features is None or bool(features & SUPPORTS_DAILY)


def days_from_daily(entries: list[dict]) -> list[dict]:
    days = []
    for entry in entries:
        when = parse_time(entry.get("datetime"))
        if when is None:
            continue
        days.append({
            "time": int(when * 1000),
            # A whole day summarised as "clear-night" is simply a clear day.
            "condition": "sunny" if entry.get("condition") == "clear-night" else entry.get("condition"),
            "high": to_float(entry.get("temperature")),
            "low": to_float(entry.get("templow")),
            "precipitation": to_float(entry.get("precipitation")),
        })
    return days[:FORECAST_DAYS]


def days_from_hourly(entries: list[dict], time_zone: str | None) -> list[dict]:
    """Daily highs and lows for providers that only publish an hourly forecast."""
    try:
        zone = ZoneInfo(time_zone) if time_zone else timezone.utc
    except ZoneInfoNotFoundError:
        zone = timezone.utc

    by_day: dict = {}
    for entry in entries:
        when = parse_time(entry.get("datetime"))
        temperature = to_float(entry.get("temperature"))
        if when is None or temperature is None:
            continue
        local = datetime.fromtimestamp(when, zone)
        day = by_day.setdefault(local.date(), {"temps": [], "rain": [], "conditions": [], "noon": local.replace(hour=12, minute=0, second=0)})
        day["temps"].append(temperature)
        day["rain"].append(to_float(entry.get("precipitation")))
        if 8 <= local.hour <= 20 and entry.get("condition"):
            day["conditions"].append(entry["condition"])

    days = []
    for date in sorted(by_day):
        day = by_day[date]
        rain = [r for r in day["rain"] if r is not None]
        conditions = day["conditions"] or [e.get("condition") for e in entries[:1]]
        days.append({
            "time": int(day["noon"].timestamp() * 1000),
            "condition": Counter(conditions).most_common(1)[0][0] if conditions else None,
            "high": max(day["temps"]),
            "low": min(day["temps"]),
            "precipitation": round(sum(rain), 1) if rain else None,
        })
    return days[:FORECAST_DAYS]


def weather_view(instance: Instance, live) -> dict | None:
    entity = weather_entity(instance, live.states)
    if not entity:
        return None
    state = live.states[entity]
    attrs = state.get("attributes") or {}
    condition = state.get("state")
    return {
        "instance": instance.name,
        "entity": entity,
        "condition": None if condition in UNAVAILABLE else condition,
        "temperature": to_float(attrs.get("temperature")),
        "unit": attrs.get("temperature_unit") or "",
        "humidity": to_float(attrs.get("humidity")),
        "wind_speed": to_float(attrs.get("wind_speed")),
        "wind_unit": attrs.get("wind_speed_unit") or "",
        "precipitation_unit": attrs.get("precipitation_unit") or "",
        "time_zone": live.time_zone,
        "stale": live.status == "error",
        "days": live.forecast if live.forecast_entity == entity else [],
    }
