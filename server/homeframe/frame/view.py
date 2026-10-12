"""What the e-paper frame shows: the family's day, the house it hangs in, and anything that needs a look."""

from __future__ import annotations

import re
import time

from ..hub import Hub
from .device import device_status

# The frame has room for two rows of six.
MAX_TEMPERATURES = 12
MAX_ATTENTION = 6

# Home Assistant weather conditions. Kept short: they render into narrow
# columns on the panel, so anything long wraps.
CONDITIONS = {
    "clear-night": "Clear", "cloudy": "Cloudy", "exceptional": "Extreme", "fog": "Fog",
    "hail": "Hail", "lightning": "Storm", "lightning-rainy": "Storm", "partlycloudy": "Partly cloudy",
    "pouring": "Heavy rain", "rainy": "Rain", "snowy": "Snow", "snowy-rainy": "Sleet",
    "sunny": "Sunny", "windy": "Windy", "windy-variant": "Windy",
}


def frame_view(hub: Hub) -> dict:
    config = hub.config
    dashboard = hub.dashboard()
    home = config.home
    status = {i["name"]: i["status"] for i in dashboard["instances"]}

    return {
        "now": int(time.time() * 1000),
        "locale": config.frame.locale,
        "time_zone": hub.time_zone,
        "hour12": config.frame.hour12,
        "home": {"name": home.name, "status": status[home.name]},
        "weather": _weather(dashboard, home.name),
        "agenda": hub.agenda,
        "todos": hub.todos,
        "temperatures": _temperatures(dashboard, home.name),
        "activity": _activity(dashboard, home.name),
        "attention": _attention(dashboard),
        "attention_more": max(0, len(dashboard["attention"]) - MAX_ATTENTION),
        "elsewhere": [_summary(dashboard, i) for i in dashboard["instances"] if i["name"] != home.name],
        "device": device_status(),
    }


def _label(condition: str | None) -> str:
    return CONDITIONS.get(condition, (condition or "").replace("-", " ").capitalize())


def _weather(dashboard: dict, home: str) -> dict | None:
    view = next((w for w in dashboard["weather"] if w["instance"] == home), None)
    if not view or view["temperature"] is None:
        return None
    days = [{**day, "condition": _label(day["condition"])} for day in view["days"]]
    return {
        "temperature": view["temperature"],
        "condition": _label(view["condition"]),
        "precipitation_unit": view["precipitation_unit"],
        # The page splits today from the days after it, in the frame's time zone.
        "days": days,
    }


def _temperatures(dashboard: dict, home: str) -> list[dict]:
    sensors = [s for panel in dashboard["panels"] if panel["instance"] == home for s in panel["sensors"]]
    return [
        {
            "name": s["name"],
            "value": s["value"],
            "status": s["status"],
            # Only a thermostat that is actually heating is worth the space.
            "target": s["climate"]["target"] if s["climate"] and s["climate"]["mode"] == "heat" else None,
        }
        for s in sensors[:MAX_TEMPERATURES]
    ]


def _activity(dashboard: dict, home: str) -> list[dict]:
    panel = next((a for a in dashboard["activity"] if a["instance"] == home), None)
    return [
        {"name": i["name"], "kind": i["kind"], "active": i["active"], "status": i["status"], "since": _ms(i["since"])}
        for i in (panel["items"] if panel else [])
    ]


def _attention(dashboard: dict) -> list[dict]:
    """Attention items cut down to what fits half a line on the panel."""
    items = []
    for item in dashboard["attention"][:MAX_ATTENTION]:
        title, detail = item["title"], item["detail"] or ""
        if item["kind"] == "instance":
            # The title is the house, which the line already starts with.
            title, detail = "Not answering", ""
        elif item["kind"] == "battery":
            title = re.sub(r"\s+battery(\s+level)?$", "", title, flags=re.IGNORECASE) or title
            detail = detail.replace("Battery at", "battery").replace("Battery low", "battery low")
        else:
            # The web dashboard's advice ("is the heating working?") does not fit.
            detail = detail.split(" — ")[0]
        items.append({"severity": item["severity"], "instance": item["instance"], "title": title, "detail": detail})
    return items


def _summary(dashboard: dict, instance: dict) -> dict:
    """One line about a house the frame does not hang in."""
    name = instance["name"]
    values = [
        s["value"] for panel in dashboard["panels"] if panel["instance"] == name
        for s in panel["sensors"] if s["value"] is not None and s["status"] != "offline"
    ]
    doors = [
        i for panel in dashboard["activity"] if panel["instance"] == name
        for i in panel["items"] if i["kind"] == "door" and i["status"] == "ok"
    ]
    return {
        "name": name,
        "status": instance["status"],
        "low": min(values, default=None),
        "high": max(values, default=None),
        "doors": len(doors),
        "open": sum(1 for d in doors if d["active"]),
        "attention": sum(1 for a in dashboard["attention"] if a["instance"] == name),
    }


def _ms(seconds: float | None) -> int | None:
    return None if seconds is None else int(seconds * 1000)
