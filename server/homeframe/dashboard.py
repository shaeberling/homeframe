"""Turns raw Home Assistant states into what the UI shows: panels and attention items."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from .config import Attention, Config, Instance, Panel, Sensor
from .ha import parse_time, to_float
from .lights import lights_view
from .people import people_view
from .weather import weather_view

OFFLINE_STATES = {"unavailable", "unknown"}

# Built-in temperature defaults per unit: thresholds and gauge range.
TEMPERATURE_DEFAULTS = {
    "°F": {"low": 61.0, "critical": 46.0, "min": 30.0, "max": 95.0},
    None: {"low": 16.0, "critical": 8.0, "min": 0.0, "max": 35.0},
}
GAUGE_RANGES = {"humidity": (0.0, 100.0), "battery": (0.0, 100.0)}

SEVERITY_ORDER = {"critical": 0, "warning": 1}


@dataclass
class InstanceState:
    states: dict[str, dict] = field(default_factory=dict)
    created: float = field(default_factory=time.time)
    last_ok: float | None = None
    error: str | None = None
    time_zone: str | None = None
    forecast: list[dict] = field(default_factory=list)
    forecast_entity: str | None = None
    forecast_at: float = 0
    # Whether Home Assistant is pushing state changes to us right now.
    push: bool = False
    # entity id → device id, so entities of one physical device can be treated as one
    devices: dict[str, str] = field(default_factory=dict)
    devices_at: float = 0
    # entity id → {"room", "floor", "level"}, from Home Assistant's areas and floors
    rooms: dict[str, dict] = field(default_factory=dict)
    rooms_at: float = 0

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "online" if self.last_ok else "connecting"


def resolve_panels(config: Config, live: dict[str, InstanceState]) -> list[tuple[str, Panel]]:
    """Configured panels, plus an auto-discovered one for instances that have none."""
    configured = [(f"panel-{n}", panel) for n, panel in enumerate(config.panels)]
    with_panels = {panel.instance for panel in config.panels}
    if all(instance.id in with_panels for instance in config.instances):
        return configured
    # Some instances still rely on discovery: keep the instances in config order.
    panels = []
    for instance in config.instances:
        if instance.id in with_panels:
            panels.extend(p for p in configured if p[1].instance == instance.id)
            continue
        found = [
            (_display_name(state, entity_id), entity_id)
            for entity_id, state in live[instance.id].states.items()
            if entity_id.startswith("sensor.") and _attrs(state).get("device_class") == "temperature"
        ]
        sensors = [Sensor(entity=entity_id) for _name, entity_id in sorted(found, key=lambda f: f[0].lower())]
        panels.append((f"auto-{instance.id}", Panel(title="Temperatures", instance=instance.id, sensors=sensors)))
    return panels


def build_dashboard(config: Config, live: dict[str, InstanceState]) -> dict:
    attention: list[dict] = []
    seen: set[tuple[str, str]] = set()
    # The name a device goes by on the dashboard: that of its first shown entity.
    labels: dict[tuple[str, str], str] = {}

    def device_of(instance: Instance, entity_id: str | None) -> tuple[str, str] | None:
        device = live[instance.id].devices.get(entity_id) if entity_id else None
        return (instance.id, device) if device else None

    def remember(instance: Instance, entity_id: str, name: str) -> None:
        device = device_of(instance, entity_id)
        if device:
            labels.setdefault(device, name)

    def label(instance: Instance, entity_id: str) -> str | None:
        return labels.get(device_of(instance, entity_id))

    def raise_attention(instance: Instance, entity_id: str | None, **item):
        if entity_id:
            if (instance.id, entity_id) in seen or _matches(config.attention.ignore, instance, entity_id):
                return
            seen.add((instance.id, entity_id))
        attention.append({
            "instance": instance.name, "entity": entity_id, "since": None,
            "device": device_of(instance, entity_id), **item,
        })

    for instance in config.instances:
        if live[instance.id].status == "error":
            raise_attention(
                instance, None,
                severity="critical", kind="instance", title=instance.name,
                detail=live[instance.id].error, key=None,
            )

    panels = []
    for panel_key, panel in resolve_panels(config, live):
        instance = config.instance(panel.instance)
        state = live[instance.id]
        sensors = []
        for sensor in panel.sensors:
            # A sensor that must not raise attention gets no thresholds either,
            # so its gauge doesn't turn red for a reading nobody wants flagged.
            alerts = sensor.alerts and not _matches(config.attention.ignore, instance, sensor.entity)
            view = _sensor_view(instance, sensor, state, config.attention, alerts)
            sensors.append(view)
            remember(instance, sensor.entity, view["name"])
            # A stale reading from an unreachable instance is not worth a second alarm.
            if alerts and state.status == "online":
                _sensor_attention(instance, view, raise_attention)
        panels.append({
            "key": panel_key,
            "title": panel.title,
            "instance": instance.name,
            "stale": state.status == "error",
            "sensors": sensors,
        })

    activity = []
    for instance in config.instances:
        if instance.activity is None:
            continue
        panel = _activity_panel(instance, live[instance.id])
        activity.append(panel)
        for item in panel["items"]:
            remember(instance, item["entity"], item["name"])
            if item["status"] == "offline" and live[instance.id].status == "online":
                raise_attention(
                    instance, item["entity"],
                    severity="critical", kind="offline", title=item["name"],
                    detail="Offline", since=item["since"], key=None,
                )

    for instance in config.instances:
        if live[instance.id].status != "online":
            continue
        for pattern in instance.batteries or []:
            if not _is_glob(pattern) and pattern not in live[instance.id].states:
                raise_attention(
                    instance, pattern,
                    severity="critical", kind="offline", title=pattern,
                    detail="Entity not found in Home Assistant", key=None,
                )
        for entity_id, state in live[instance.id].states.items():
            is_battery = _is_watched_battery(instance, entity_id, state)
            watched = _matches(config.attention.watch, instance, entity_id)
            raw = state.get("state")
            if (is_battery or watched) and raw == "unavailable":
                raise_attention(
                    instance, entity_id,
                    severity="critical", kind="offline", title=_display_name(state, entity_id),
                    detail="Offline", since=parse_time(state.get("last_changed")), key=None,
                )
            elif is_battery:
                detail = _battery_detail(entity_id, raw, config.attention)
                if detail:
                    raise_attention(
                        instance, entity_id,
                        severity="warning", kind="battery",
                        title=label(instance, entity_id) or _display_name(state, entity_id),
                        detail=detail, key=None,
                    )

    attention = _merge_offline_devices(attention, labels)
    attention.sort(key=lambda a: (SEVERITY_ORDER[a["severity"]], a["instance"], a["title"].lower()))

    return {
        "demo": config.demo,
        "poll_interval": config.poll_interval,
        "stale_after": config.stale_after * 60,
        "instances": [
            {
                "id": instance.id,
                "name": instance.name,
                "status": live[instance.id].status,
                "error": live[instance.id].error,
                "last_update": live[instance.id].last_ok,
                # seconds since the instance last answered (or, if it never did, since startup)
                "age": time.time() - (live[instance.id].last_ok or live[instance.id].created),
                "entities": len(live[instance.id].states),
                "push": live[instance.id].push,
            }
            for instance in config.instances
        ],
        "weather": [
            view for instance in config.instances
            if (view := weather_view(instance, live[instance.id])) is not None
        ],
        "people": people_view(config, live),
        "panels": panels,
        "activity": activity,
        "lights": [
            lights_view(instance, live[instance.id])
            for instance in config.instances if instance.lights is not None
        ],
        "batteries": [
            _battery_panel(instance, live[instance.id], config.attention, label)
            for instance in config.instances if instance.batteries is not None or instance.all_batteries
        ],
        "attention": attention,
    }


def _merge_offline_devices(attention: list[dict], labels: dict) -> list[dict]:
    """One "offline" entry per physical device, however many of its entities are shown or watched."""
    merged: list[dict] = []
    offline: dict[tuple[str, str], dict] = {}
    for item in attention:
        device = item.pop("device")
        if item["kind"] == "offline" and device:
            first = offline.get(device)
            if first:
                first["key"] = first["key"] or item["key"]
                if item["since"] and (not first["since"] or item["since"] < first["since"]):
                    first["since"] = item["since"]
                continue
            offline[device] = item
            item["title"] = labels.get(device, item["title"])
        merged.append(item)
    return merged


def _sensor_view(instance: Instance, sensor: Sensor, live: InstanceState, attention: Attention, alerts: bool) -> dict:
    state = live.states.get(sensor.entity)
    attrs = _attrs(state)
    unit = attrs.get("unit_of_measurement") or ""
    device_class = attrs.get("device_class")
    is_temperature = device_class == "temperature" or unit in ("°C", "°F")
    raw = state.get("state") if state else None
    value = to_float(raw)

    low = critical = None
    gauge_min, gauge_max = GAUGE_RANGES.get(device_class, (0.0, 100.0))
    if is_temperature:
        defaults = TEMPERATURE_DEFAULTS.get(unit, TEMPERATURE_DEFAULTS[None])
        if alerts:
            low = _first(sensor.low, attention.temperature_low, defaults["low"])
            critical = _first(sensor.critical, attention.temperature_critical, defaults["critical"])
        gauge_min, gauge_max = defaults["min"], defaults["max"]
    gauge_min = _first(sensor.min, gauge_min)
    gauge_max = _first(sensor.max, gauge_max)

    note = None
    if not live.last_ok:
        status = "nodata"
    elif state is None:
        status, note = "offline", "Entity not found in Home Assistant"
    elif raw in OFFLINE_STATES:
        status = "offline"
    elif value is None:
        status = "nodata"
    elif critical is not None and value < critical:
        status = "critical"
    elif low is not None and value < low:
        status = "low"
    else:
        status = "ok"

    humidity = None
    if sensor.humidity:
        humidity_state = live.states.get(sensor.humidity)
        humidity = {
            "value": to_float(humidity_state.get("state")) if humidity_state else None,
            "unit": _attrs(humidity_state).get("unit_of_measurement") or "%",
        }

    climate = None
    if sensor.climate:
        climate_state = live.states.get(sensor.climate)
        mode = climate_state.get("state") if climate_state else None
        climate = {
            "mode": None if mode is None or mode in OFFLINE_STATES else mode,
            "target": to_float(_attrs(climate_state).get("temperature")),
            "preset": _attrs(climate_state).get("preset_mode"),
        }

    return {
        "key": f"{instance.id}:{sensor.entity}",
        "entity": sensor.entity,
        "humidity": humidity,
        "climate": climate,
        "name": sensor.name or _display_name(state, sensor.entity, strip_kind=True),
        "value": value,
        "unit": unit,
        "status": status,
        "note": note,
        "min": gauge_min,
        "max": gauge_max,
        "low": low,
        "critical": critical,
        "since": parse_time(state.get("last_changed")) if state else None,
    }


def _sensor_attention(instance: Instance, view: dict, raise_attention) -> None:
    status = view["status"]
    common = {"title": view["name"], "key": view["key"]}
    if status == "offline":
        raise_attention(
            instance, view["entity"],
            severity="critical", kind="offline",
            detail=view["note"] or "Offline", since=None if view["note"] else view["since"], **common,
        )
    elif status == "critical":
        raise_attention(
            instance, view["entity"],
            severity="critical", kind="temperature",
            detail=f"{_reading(view)} · below {_threshold(view, 'critical')} — is the heating working?", **common,
        )
    elif status == "low":
        raise_attention(
            instance, view["entity"],
            severity="warning", kind="temperature",
            detail=f"{_reading(view)} · below {_threshold(view, 'low')}", **common,
        )


# "garage" and "gate" are what a cover entity (a garage door opener) calls itself.
DOOR_CLASSES = {"door", "opening", "window", "garage_door", "garage", "gate"}
MOTION_CLASSES = {"motion", "occupancy", "presence", "moving"}
# Covers that are opened and closed as a matter of course. They are listed, but
# an open one is not an event the way an open door is.
SHADE_CLASSES = {"shutter", "blind", "shade", "curtain", "awning"}
# A cover reports where it is rather than on/off; anything but closed counts as open.
COVER_STATES = {"open": "on", "opening": "on", "closing": "on", "closed": "off"}


ACTIVITY_KINDS = {"door": DOOR_CLASSES, "motion": MOTION_CLASSES, "shade": SHADE_CLASSES}


def activity_state(raw: str | None) -> str | None:
    """The state of a door or motion sensor as on/off, whatever kind of entity reports it."""
    return COVER_STATES.get(raw, raw)


def activity_item(instance: Instance, live: InstanceState, entity_id: str) -> dict | None:
    return next((i for i in _activity_panel(instance, live)["items"] if i["entity"] == entity_id), None)


def _activity_panel(instance: Instance, live: InstanceState) -> dict:
    """Door and motion sensors with their state and the time it last changed."""
    items = []
    for entry in instance.activity or []:
        state = live.states.get(entry.entity)
        raw = state.get("state") if state else None
        device_class = _attrs(state).get("device_class")
        if not live.last_ok:
            status = "nodata"
        elif state is None or raw in OFFLINE_STATES:
            status = "offline"
        else:
            status = "ok"
        items.append({
            "entity": entry.entity,
            "name": entry.name or _display_name(state, entry.entity),
            "kind": next((kind for kind, classes in ACTIVITY_KINDS.items() if device_class in classes), "other"),
            "active": activity_state(raw) == "on" if status == "ok" else None,
            "status": status,
            "since": parse_time(state.get("last_changed")) if state else None,
        })
    return {
        "key": f"activity-{instance.id}",
        "instance_id": instance.id,
        "instance": instance.name,
        "stale": live.status == "error",
        "items": items,
    }


def _is_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _is_watched_battery(instance: Instance, entity_id: str, state: dict) -> bool:
    if instance.batteries is not None:
        return any(fnmatchcase(entity_id, pattern) for pattern in instance.batteries)
    return _attrs(state).get("device_class") == "battery"


def _battery_panel(instance: Instance, live: InstanceState, attention: Attention, label) -> dict:
    """The battery sensors an instance lists (or all it has, if it asks for that), emptiest first."""
    entities: list[str] = []
    if instance.batteries is None:
        entities = sorted(e for e, state in live.states.items() if _is_watched_battery(instance, e, state))
    for pattern in instance.batteries or []:
        matches = sorted(e for e in live.states if fnmatchcase(e, pattern)) if _is_glob(pattern) else [pattern]
        entities.extend(e for e in matches if e not in entities)

    items = []
    for entity_id in entities:
        state = live.states.get(entity_id)
        raw = state.get("state") if state else None
        level = to_float(raw)
        if not live.last_ok:
            status = "nodata"
        elif state is None or raw in OFFLINE_STATES:
            status = "offline"
        elif _battery_detail(entity_id, raw, attention):
            status = "low"
        else:
            status = "ok"
        name = _display_name(state, entity_id)
        items.append({
            "entity": entity_id,
            # Same name as the device has elsewhere on the dashboard, if it is shown there.
            "name": label(instance, entity_id) or re.sub(r"\s+battery(\s+level)?$", "", name, flags=re.IGNORECASE) or name,
            "level": level,
            "status": status,
        })
    # Emptiest on top, fullest at the bottom. Some sensors only report "low" or
    # "ok": a bare "low" counts as empty, a bare "ok" as full.
    order = {"offline": 0, "nodata": 0, "low": 1}

    def emptiness(item: dict) -> tuple:
        level = item["level"]
        if level is None:
            level = 101 if item["status"] == "ok" else -1
        return order.get(item["status"], 2), level, item["name"].lower()

    items.sort(key=emptiness)
    return {
        "key": f"batteries-{instance.id}",
        "instance": instance.name,
        "stale": live.status == "error",
        "items": items,
    }


def _battery_detail(entity_id: str, raw, attention: Attention) -> str | None:
    if entity_id.startswith("binary_sensor."):
        return "Battery low" if raw == "on" else None
    level = to_float(raw)
    if level is not None and level <= attention.battery_low:
        return f"Battery at {level:g} %"
    return None


def _reading(view: dict) -> str:
    return f"{view['value']:.1f} {view['unit']}".strip()


def _threshold(view: dict, which: str) -> str:
    return f"{view[which]:g} {view['unit']}".strip()


def _attrs(state: dict | None) -> dict:
    return (state or {}).get("attributes") or {}


def _display_name(state: dict | None, entity_id: str, strip_kind: bool = False) -> str:
    name = _attrs(state).get("friendly_name") or entity_id
    if strip_kind:
        # "Living room temperature" is redundant on a temperature gauge.
        name = re.sub(r"\s+temperature$", "", name, flags=re.IGNORECASE) or name
    return name


def _matches(patterns: list[str], instance: Instance, entity_id: str) -> bool:
    qualified = f"{instance.id}:{entity_id}"
    return any(fnmatchcase(entity_id, p) or fnmatchcase(qualified, p) for p in patterns)


def _first(*values):
    return next((v for v in values if v is not None), None)
