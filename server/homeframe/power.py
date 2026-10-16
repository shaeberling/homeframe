"""What a house draws right now: the total, and the circuits that make it up.

Typically an energy monitor in the electrical panel (an Emporia Vue, a Shelly
EM, an IoTaWatt): one power sensor for the mains and one per clamped circuit.
"""

from __future__ import annotations

from .config import Instance
from .ha import to_float

OFFLINE = {"unavailable", "unknown", None}
# Power in watts, whatever unit the sensor reports it in.
TO_WATTS = {"W": 1, "kW": 1000, "MW": 1_000_000}
# Energy in kilowatt-hours.
TO_KWH = {"Wh": 0.001, "kWh": 1, "MWh": 1000}


def _reading(states: dict[str, dict], entity_id: str | None, units: dict[str, float]) -> float | None:
    state = states.get(entity_id) if entity_id else None
    if not state or state.get("state") in OFFLINE:
        return None
    value = to_float(state.get("state"))
    unit = (state.get("attributes") or {}).get("unit_of_measurement")
    return value * units.get(unit, 1) if value is not None else None


def _status(states: dict[str, dict], entity_id: str | None) -> str | None:
    raw = (states.get(entity_id) or {}).get("state") if entity_id else None
    return None if raw in OFFLINE else str(raw)


def power_view(instance: Instance, live) -> dict:
    power = instance.power
    states = live.states
    circuits = []
    for circuit in power.circuits:
        state = states.get(circuit.entity)
        watts = _reading(states, circuit.entity, TO_WATTS)
        circuits.append({
            "entity": circuit.entity,
            "name": circuit.name or ((state or {}).get("attributes") or {}).get("friendly_name") or circuit.entity,
            "watts": watts,
            "status": _status(states, circuit.status),
            "offline": watts is None,
        })
    total = _reading(states, power.total, TO_WATTS)
    if power.total is None:
        # Without a mains sensor, the circuits are all there is.
        known = [c["watts"] for c in circuits if c["watts"] is not None]
        total = sum(known) if known else None
    return {
        "key": f"power-{instance.id}",
        "instance": instance.name,
        "stale": live.status == "error",
        "total": total,
        "today": _reading(states, power.energy, TO_KWH),
        "circuits": circuits,
    }
