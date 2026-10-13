from homeframe.config import Attention, Instance
from homeframe.dashboard import InstanceState, _battery_panel


def battery(entity, value, name):
    return {"entity_id": entity, "state": value, "attributes": {"friendly_name": name, "device_class": "battery"}}


def test_batteries_run_from_empty_at_the_top_to_full_at_the_bottom():
    states = [
        battery("sensor.full", "100", "Full"),
        battery("binary_sensor.fine", "off", "Fine"),  # only reports ok or low
        battery("sensor.half", "55", "Half"),
        battery("binary_sensor.flat", "on", "Flat"),
        battery("sensor.weak", "12", "Weak"),
        battery("sensor.gone", "unavailable", "Gone"),
        battery("sensor.good", "80", "Good"),
    ]
    live = InstanceState(states={s["entity_id"]: s for s in states}, last_ok=1.0)
    instance = Instance(id="home", name="Home", url="http://ha", token="t", all_batteries=True)

    panel = _battery_panel(instance, live, Attention(), lambda _instance, _entity: None)

    assert [i["name"] for i in panel["items"]] == ["Gone", "Flat", "Weak", "Half", "Good", "Full", "Fine"]
