"""Loading and validating config.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


@dataclass
class ActivityItem:
    entity: str
    name: str | None = None


@dataclass
class Instance:
    id: str
    name: str
    url: str
    token: str
    verify_ssl: bool = True
    # Weather entity for the forecast: None picks one automatically, False hides it.
    weather: str | bool | None = None
    # Battery sensors (ids or globs) to watch and list; None watches every battery sensor.
    batteries: list[str] | None = None
    # Door and motion sensors listed with their state and last change. None
    # leaves the panel out; an empty list shows it, waiting for its sensors.
    activity: list[ActivityItem] | None = None


@dataclass
class Sensor:
    entity: str
    name: str | None = None
    humidity: str | None = None  # companion humidity sensor shown on the same card
    climate: str | None = None  # companion thermostat: heating mode and target on the same card
    min: float | None = None
    max: float | None = None
    low: float | None = None
    critical: float | None = None
    alerts: bool = True


@dataclass
class Panel:
    title: str
    instance: str
    sensors: list[Sensor]


@dataclass
class Attention:
    battery_low: float = 20
    # None means "use the built-in default for the sensor's unit".
    temperature_low: float | None = None
    temperature_critical: float | None = None
    watch: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)


@dataclass
class Frame:
    """The e-paper panel: what it shows and how the page becomes a 1bpp frame."""

    # Instance of the house the frame hangs in; None means the first one.
    home: str | None = None
    # "landscape" renders the page at 960x680 directly. "portrait" renders at
    # 680x960 and rotates into the panel's native scanline order. Must agree
    # with HF_DISPLAY_ROTATION in the firmware.
    orientation: str = "landscape"
    # Greyscale cutoff, 0-255. Text stays crisp with a hard threshold; dither
    # only when the frame carries photos.
    threshold: int = 160
    dither: bool = False
    # Re-render at most this often (seconds), however many devices are polling.
    render_ttl: float = 30
    # Must match HF_SERVER_TOKEN in the firmware. Empty disables the check.
    token: str = ""
    # Browser binary; None looks for a system Chromium, then Playwright's own.
    chrome_path: str | None = None
    locale: str = "en-US"
    # IANA zone for the clock and agenda; None uses Home Assistant's.
    time_zone: str | None = None
    hour12: bool = False


@dataclass
class Calendar:
    # Instance to read calendars from; None means the frame's home instance.
    instance: str | None = None
    # calendar.* entities; None reads every calendar the instance has.
    entities: list[str] | None = None
    # Only events whose title starts with one of these are shown.
    prefixes: list[str] = field(default_factory=lambda: ["⭐", "🌟", "★"])
    days: int = 14
    limit: int = 6


@dataclass
class Todo:
    instance: str | None = None
    # todo.* entities; None reads every to-do list the instance has.
    entities: list[str] | None = None
    limit: int = 8


@dataclass
class Config:
    instances: list[Instance]
    panels: list[Panel] = field(default_factory=list)
    attention: Attention = field(default_factory=Attention)
    frame: Frame = field(default_factory=Frame)
    calendar: Calendar = field(default_factory=Calendar)
    todo: Todo = field(default_factory=Todo)
    # The IPv4 wildcard, so the ESP32 can reach /frame.bin.
    host: str = "0.0.0.0"
    port: int = 8080
    poll_interval: float = 15
    stale_after: float = 15  # minutes without an update before the UI raises the alarm
    demo: bool = False

    def instance(self, instance_id: str) -> Instance:
        return next(i for i in self.instances if i.id == instance_id)

    @property
    def home(self) -> Instance:
        """The instance of the house the frame hangs in."""
        return self.instance(self.frame.home) if self.frame.home else self.instances[0]


def load_config(path: Path) -> Config:
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")

    instances = [_instance(i, n) for n, i in enumerate(_list(raw, "instances"), 1)]
    if not instances:
        raise ConfigError("instances: define at least one Home Assistant instance")
    ids = [i.id for i in instances]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"instances: ids must be unique, got {', '.join(ids)}")

    panels = [_panel(p, n, ids) for n, p in enumerate(_list(raw, "panels"), 1)]

    server = _mapping(raw, "server")
    services = _mapping(raw, "services")
    return Config(
        instances=instances,
        panels=panels,
        attention=_attention(_mapping(raw, "attention")),
        frame=_frame(_mapping(raw, "frame"), ids),
        calendar=_calendar(_mapping(services, "calendar"), ids),
        todo=_todo(_mapping(services, "todo"), ids),
        host=str(server.get("host", "0.0.0.0")),
        port=int(server.get("port", 8080)),
        poll_interval=max(2.0, _number(server, "poll_interval", "server") or 15),
        stale_after=max(1.0, _number(server, "stale_after", "server") or 15),
    )


def _instance(raw, n: int) -> Instance:
    where = f"instances[{n}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a mapping with name, url and token")
    name = str(raw.get("name") or raw.get("id") or "").strip()
    if not name:
        raise ConfigError(f"{where}: name is required")
    url = str(raw.get("url") or "").strip().rstrip("/")
    if not re.match(r"https?://", url):
        raise ConfigError(f"{where} ({name}): url must start with http:// or https://")
    token = str(raw.get("token") or "").strip()
    if not token or token.startswith("PASTE_"):
        raise ConfigError(f"{where} ({name}): token is missing")
    instance_id = str(raw.get("id") or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))
    weather = raw.get("weather")
    if weather is True:
        weather = None
    if not (weather is None or weather is False or (isinstance(weather, str) and weather.startswith("weather."))):
        raise ConfigError(f"{where} ({name}): weather must be a weather.* entity id or false")
    return Instance(
        id=instance_id,
        name=name,
        url=url,
        token=token,
        verify_ssl=bool(raw.get("verify_ssl", True)),
        weather=weather,
        batteries=[str(b) for b in _list(raw, "batteries", where)] if raw.get("batteries") is not None else None,
        activity=(
            [_activity(a, f"{where}.activity[{m}]") for m, a in enumerate(_list(raw, "activity", where), 1)]
            if "activity" in raw else None
        ),
    )


def _activity(raw, where: str) -> ActivityItem:
    if isinstance(raw, str):
        raw = {"entity": raw}
    if not isinstance(raw, dict) or not raw.get("entity"):
        raise ConfigError(f"{where}: expected an entity id or a mapping with an entity key")
    return ActivityItem(entity=str(raw["entity"]).strip(), name=str(raw["name"]) if raw.get("name") else None)


def _panel(raw, n: int, instance_ids: list[str]) -> Panel:
    where = f"panels[{n}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a mapping with title, instance and sensors")
    instance = raw.get("instance")
    if instance is None and len(instance_ids) == 1:
        instance = instance_ids[0]
    if instance not in instance_ids:
        raise ConfigError(
            f"{where}: instance must be one of {', '.join(instance_ids)} (got {instance!r})"
        )
    sensors = [_sensor(s, f"{where}.sensors[{m}]") for m, s in enumerate(_list(raw, "sensors", where), 1)]
    if not sensors:
        raise ConfigError(f"{where}: sensors is empty")
    return Panel(title=str(raw.get("title") or f"Panel {n}"), instance=instance, sensors=sensors)


def _sensor(raw, where: str) -> Sensor:
    if isinstance(raw, str):
        raw = {"entity": raw}
    if not isinstance(raw, dict) or not raw.get("entity"):
        raise ConfigError(f"{where}: expected an entity id or a mapping with an entity key")
    return Sensor(
        entity=str(raw["entity"]).strip(),
        name=str(raw["name"]) if raw.get("name") else None,
        humidity=str(raw["humidity"]) if raw.get("humidity") else None,
        climate=str(raw["climate"]) if raw.get("climate") else None,
        min=_number(raw, "min", where),
        max=_number(raw, "max", where),
        low=_number(raw, "low", where),
        critical=_number(raw, "critical", where),
        alerts=bool(raw.get("alerts", True)),
    )


def _attention(raw: dict) -> Attention:
    battery_low = _number(raw, "battery_low", "attention")
    return Attention(
        battery_low=20 if battery_low is None else battery_low,
        temperature_low=_number(raw, "temperature_low", "attention"),
        temperature_critical=_number(raw, "temperature_critical", "attention"),
        watch=[str(p) for p in _list(raw, "watch", "attention")],
        ignore=[str(p) for p in _list(raw, "ignore", "attention")],
    )


def _frame(raw: dict, instance_ids: list[str]) -> Frame:
    orientation = str(raw.get("orientation", "landscape")).lower()
    if orientation not in ("landscape", "portrait"):
        raise ConfigError(f"frame.orientation: expected landscape or portrait, got {orientation!r}")
    threshold = _number(raw, "threshold", "frame")
    render_ttl = _number(raw, "render_ttl", "frame")
    clock = raw.get("clock", 24)
    if clock not in (12, 24):
        raise ConfigError(f"frame.clock: expected 12 or 24, got {clock!r}")
    return Frame(
        home=_instance_ref(raw, "home", "frame", instance_ids),
        orientation=orientation,
        threshold=160 if threshold is None else int(min(255, max(0, threshold))),
        dither=bool(raw.get("dither", False)),
        render_ttl=30 if render_ttl is None else max(0.0, render_ttl),
        token=str(raw.get("token") or ""),
        chrome_path=str(raw["chrome_path"]) if raw.get("chrome_path") else None,
        locale=str(raw.get("locale") or "en-US"),
        time_zone=str(raw["time_zone"]) if raw.get("time_zone") else None,
        hour12=clock == 12,
    )


def _calendar(raw: dict, instance_ids: list[str]) -> Calendar:
    where = "services.calendar"
    defaults = Calendar()
    prefixes = [str(p) for p in _list(raw, "prefixes", where)] or defaults.prefixes
    return Calendar(
        instance=_instance_ref(raw, "instance", where, instance_ids),
        entities=_entities(raw, where, "calendar."),
        prefixes=prefixes,
        days=int(_number(raw, "days", where) or defaults.days),
        limit=int(_number(raw, "limit", where) or defaults.limit),
    )


def _todo(raw: dict, instance_ids: list[str]) -> Todo:
    where = "services.todo"
    return Todo(
        instance=_instance_ref(raw, "instance", where, instance_ids),
        entities=_entities(raw, where, "todo."),
        limit=int(_number(raw, "limit", where) or Todo().limit),
    )


def _instance_ref(raw: dict, key: str, where: str, instance_ids: list[str]) -> str | None:
    value = raw.get(key)
    if value is not None and value not in instance_ids:
        raise ConfigError(f"{where}.{key}: must be one of {', '.join(instance_ids)} (got {value!r})")
    return value


def _entities(raw: dict, where: str, domain: str) -> list[str] | None:
    """An explicit entity list; None when the key is left out (discover them)."""
    if raw.get("entities") is None:
        return None
    entities = [str(e).strip() for e in _list(raw, "entities", where)]
    for entity in entities:
        if not entity.startswith(domain):
            raise ConfigError(f"{where}.entities: {entity!r} is not a {domain}* entity")
    return entities


def _mapping(raw: dict, key: str) -> dict:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"{key}: expected a mapping")
    return value


def _list(raw: dict, key: str, where: str = "") -> list:
    value = raw.get(key) or []
    if not isinstance(value, list):
        raise ConfigError(f"{where + '.' if where else ''}{key}: expected a list")
    return value


def _number(raw: dict, key: str, where: str) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}.{key}: expected a number, got {value!r}")
    return float(value)
