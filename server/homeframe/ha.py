"""Minimal Home Assistant REST client."""

from __future__ import annotations

import asyncio
import json
import math
import ssl
from datetime import datetime, timezone

import httpx
import websockets

from .config import Instance

# One history series: (epoch seconds, value). None marks a period without a
# usable reading (unavailable/unknown), so charts can break the line there.
Series = list[tuple[float, float | None]]


def to_float(raw) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def parse_time(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def _epoch(raw) -> float | None:
    """Statistics timestamps are epoch milliseconds (ISO strings on older versions)."""
    if isinstance(raw, (int, float)):
        return raw / 1000
    return parse_time(raw)


def _iso_z(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HAClient:
    def __init__(self, instance: Instance):
        self.instance = instance
        self._http = httpx.AsyncClient(
            base_url=f"{instance.url}/api",
            headers={"Authorization": f"Bearer {instance.token}"},
            verify=instance.verify_ssl,
            # Connecting includes the name lookup, and a resolver that drops one of
            # the A/AAAA queries answers after its own 5 s retry.
            timeout=httpx.Timeout(30, connect=10),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def states(self) -> list[dict]:
        response = await self._http.get("/states")
        response.raise_for_status()
        return response.json()

    async def time_zone(self) -> str | None:
        response = await self._http.get("/config")
        response.raise_for_status()
        return response.json().get("time_zone")

    async def forecast(self, entity_id: str, kind: str) -> list[dict]:
        """Forecast entries of a weather entity; kind is "daily" or "hourly"."""
        response = await self._http.post(
            "/services/weather/get_forecasts",
            params={"return_response": "1"},
            json={"entity_id": entity_id, "type": kind},
        )
        response.raise_for_status()
        answer = response.json().get("service_response") or {}
        return (answer.get(entity_id) or {}).get("forecast") or []

    async def calendar_events(self, entity_id: str, start: datetime, end: datetime) -> list[dict]:
        """Events of a calendar entity that overlap the window, as Home Assistant reports them."""
        response = await self._http.get(
            f"/calendars/{entity_id}", params={"start": _iso_z(start), "end": _iso_z(end)}
        )
        response.raise_for_status()
        return response.json()

    async def todo_items(self, entity_id: str) -> list[dict]:
        """Open items of a to-do list entity."""
        response = await self._http.post(
            "/services/todo/get_items",
            params={"return_response": "1"},
            json={"entity_id": entity_id, "status": ["needs_action"]},
        )
        response.raise_for_status()
        answer = response.json().get("service_response") or {}
        return (answer.get(entity_id) or {}).get("items") or []

    def _socket(self):
        """A connection to the WebSocket API, not yet authenticated."""
        url = self.instance.url.replace("http", "ws", 1) + "/api/websocket"
        options = {}
        if url.startswith("wss://") and not self.instance.verify_ssl:
            options["ssl"] = ssl._create_unverified_context()
        return websockets.connect(url, max_size=None, **options)

    async def _ask(self, socket, command: dict):
        """Authenticate, send one command and return its result."""
        await socket.recv()  # auth_required
        await socket.send(json.dumps({"type": "auth", "access_token": self.instance.token}))
        if json.loads(await socket.recv()).get("type") != "auth_ok":
            raise PermissionError("Access denied — check the access token")
        await socket.send(json.dumps({"id": 1, **command}))
        answer = json.loads(await socket.recv())
        if not answer.get("success"):
            raise RuntimeError((answer.get("error") or {}).get("message") or f"{command['type']} failed")
        return answer.get("result")

    async def _command(self, command: dict):
        """Run one command over the WebSocket API and return its result."""
        async with asyncio.timeout(45):
            async with self._socket() as socket:
                return await self._ask(socket, command)

    async def _commands(self, commands: list[dict]) -> list:
        """Run several commands over one connection; a command that fails yields None."""
        async with asyncio.timeout(60):
            async with self._socket() as socket:
                results = [await self._ask(socket, commands[0])]
                for number, command in enumerate(commands[1:], 2):
                    await socket.send(json.dumps({"id": number, **command}))
                    answer = json.loads(await socket.recv())
                    results.append(answer.get("result") if answer.get("success") else None)
                return results

    async def listen(self, on_change, on_ready) -> None:
        """Stay connected and report every state change the moment it happens.

        on_change(entity_id, state) gets the new state, or None for an entity
        that was removed. Returns when Home Assistant closes the connection
        and raises when it breaks; either way the caller connects again.
        """
        async with self._socket() as socket:
            async with asyncio.timeout(30):
                await self._ask(socket, {"type": "subscribe_events", "event_type": "state_changed"})
            on_ready()
            async for message in socket:
                event = json.loads(message)
                if event.get("type") == "event":
                    change = event["event"]["data"]
                    on_change(change["entity_id"], change.get("new_state"))

    async def entity_devices(self) -> dict[str, str]:
        """Which device each entity belongs to (entity id → device id)."""
        entries = await self._command({"type": "config/entity_registry/list"}) or []
        return {e["entity_id"]: e["device_id"] for e in entries if e.get("device_id")}

    async def entity_rooms(self) -> dict[str, dict]:
        """Where each entity is: {"room", "floor", "level"}, as far as Home Assistant has been told.

        An entity is in the area set on it, or else in its device's. Floors
        are optional in Home Assistant (and missing altogether before 2024.4).
        """
        entities, devices, areas, floors = await self._commands([
            {"type": "config/entity_registry/list"},
            {"type": "config/device_registry/list"},
            {"type": "config/area_registry/list"},
            {"type": "config/floor_registry/list"},
        ])
        device_area = {d["id"]: d.get("area_id") for d in devices or []}
        floor_of = {f["floor_id"]: f for f in floors or []}
        area_of = {a["area_id"]: a for a in areas or []}
        rooms = {}
        for entity in entities or []:
            area = area_of.get(entity.get("area_id") or device_area.get(entity.get("device_id")))
            if not area:
                continue
            floor = floor_of.get(area.get("floor_id")) or {}
            rooms[entity["entity_id"]] = {"room": area["name"], "floor": floor.get("name"), "level": floor.get("level")}
        return rooms

    async def statistics(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        """Hourly means from the long-term statistics.

        Home Assistant keeps raw history for about ten days; statistics go
        back much further but are only offered over the WebSocket API.
        """
        if not entity_ids:
            return {}
        rows_by_entity = await self._command({
            "type": "recorder/statistics_during_period",
            "start_time": _iso_z(start),
            "end_time": _iso_z(end),
            "statistic_ids": entity_ids,
            "period": "hour",
            "types": ["mean"],
        })

        result: dict[str, Series] = {}
        for entity_id, rows in (rows_by_entity or {}).items():
            series: Series = []
            for row in rows:
                when, value = _epoch(row.get("start")), to_float(row.get("mean"))
                if when is None or value is None:
                    continue
                # Hours without statistics mean the sensor reported nothing: show a gap.
                if series and when - series[-1][0] > 2.5 * 3600:
                    series.append((series[-1][0] + 3600, None))
                series.append((when, value))
            result[entity_id] = series
        return result

    async def state_changes(self, entity_id: str, start: datetime, end: datetime) -> list[tuple[float, str]]:
        """Every recorded state change of one entity as (epoch seconds, state), oldest first."""
        response = await self._http.get(
            f"/history/period/{_iso_z(start)}",
            params={"filter_entity_id": entity_id, "end_time": _iso_z(end), "minimal_response": "1", "no_attributes": "1"},
        )
        response.raise_for_status()
        changes: list[tuple[float, str]] = []
        for rows in response.json():
            for row in rows:
                when = parse_time(row.get("last_changed") or row.get("last_updated"))
                state = row.get("state")
                if when is not None and state is not None and (not changes or changes[-1][1] != state):
                    changes.append((when, state))
        return changes

    async def history(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, Series]:
        if not entity_ids:
            return {}
        response = await self._http.get(
            f"/history/period/{_iso_z(start)}",
            params={
                "filter_entity_id": ",".join(entity_ids),
                "end_time": _iso_z(end),
                "minimal_response": "1",
                "no_attributes": "1",
            },
        )
        response.raise_for_status()

        result: dict[str, Series] = {}
        for rows in response.json():
            if not rows:
                continue
            # With minimal_response only the first row carries the entity id.
            entity_id = rows[0].get("entity_id")
            series: Series = []
            for row in rows:
                when = parse_time(row.get("last_changed") or row.get("last_updated"))
                if when is not None:
                    series.append((when, to_float(row.get("state"))))
            if entity_id:
                result[entity_id] = series
        return result


def describe_error(error: Exception, instance: Instance) -> str:
    cause = str(error)
    if "WRONG_VERSION_NUMBER" in cause:
        return f"{instance.url} answers plain HTTP on this port — should the URL start with http://?"
    if "CERTIFICATE_VERIFY_FAILED" in cause:
        return f"The TLS certificate of {instance.url} could not be verified"

    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        if code in (401, 403):
            return "Access denied — check the access token"
        return f"Home Assistant answered HTTP {code}"
    if isinstance(error, httpx.TimeoutException):
        return f"Timed out connecting to {instance.url}"
    if isinstance(error, httpx.ConnectError):
        return f"Cannot connect to {instance.url}" + (f" ({cause})" if cause else "")
    if isinstance(error, (PermissionError, TimeoutError)):
        return cause or "Timed out talking to Home Assistant"
    return f"{type(error).__name__}: {cause}"
