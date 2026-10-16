from types import SimpleNamespace

import pytest

from homeframe.config import Circuit, ConfigError, Instance, Power, _power
from homeframe.power import power_view


def reading(entity_id, state, unit=None, name=None):
    return {"entity_id": entity_id, "state": state, "attributes": {"friendly_name": name or entity_id, "unit_of_measurement": unit}}


def view(power, *states):
    house = Instance(id="home", name="Home", url="http://ha", token="t", power=power)
    live = SimpleNamespace(states={s["entity_id"]: s for s in states}, status="online")
    return power_view(house, live)


def test_power_is_in_watts_and_energy_in_kilowatt_hours_whatever_the_sensors_report():
    result = view(
        Power(total="sensor.mains", energy="sensor.today", circuits=[Circuit("sensor.oven"), Circuit("sensor.car", "Car", "sensor.car_status")]),
        reading("sensor.mains", "1.25", "kW"),
        reading("sensor.today", "14300", "Wh"),
        reading("sensor.oven", "800", "W", "Oven Power"),
        reading("sensor.car", "unavailable", "W"),
        reading("sensor.car_status", "Charging"),
    )
    assert result["total"] == 1250 and result["today"] == 14.3
    oven, car = result["circuits"]
    assert (oven["name"], oven["watts"], oven["offline"]) == ("Oven Power", 800, False)
    assert (car["name"], car["watts"], car["offline"], car["status"]) == ("Car", None, True, "Charging")


def test_without_a_mains_sensor_the_circuits_add_up_to_the_total():
    result = view(Power(circuits=[Circuit("sensor.a"), Circuit("sensor.b")]), reading("sensor.a", "100", "W"), reading("sensor.b", "250", "W"))
    assert result["total"] == 350 and result["today"] is None


def test_the_power_config_takes_ids_or_mappings_and_needs_something_to_show():
    power = _power({"total": "sensor.mains", "circuits": ["sensor.a", {"entity": "sensor.b", "name": "B", "status": "sensor.s"}]}, "power")
    assert power.circuits == [Circuit("sensor.a"), Circuit("sensor.b", "B", "sensor.s")]
    assert _power(None, "power") is None
    with pytest.raises(ConfigError):
        _power({"energy": "sensor.today"}, "power")
