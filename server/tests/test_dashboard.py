from homeframe.config import Attention, Instance, Sensor
from homeframe.dashboard import InstanceState, _battery_panel, humidity_of, last_real_change


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


def test_a_sensor_gets_the_humidity_of_its_own_device_unless_one_is_named():
    def sensor(entity, kind):
        return {"entity_id": entity, "state": "50", "attributes": {"device_class": kind}}

    states = [
        sensor("sensor.hall_temperature", "temperature"), sensor("sensor.hall_humidity", "humidity"),
        sensor("sensor.hall_battery", "battery"), sensor("sensor.attic_temperature", "temperature"),
        sensor("sensor.attic_humidity", "humidity"),
    ]
    live = InstanceState(states={s["entity_id"]: s for s in states}, last_ok=1.0)
    live.devices = {
        "sensor.hall_temperature": "hall", "sensor.hall_humidity": "hall", "sensor.hall_battery": "hall",
        "sensor.attic_temperature": "attic", "sensor.attic_humidity": "other",
    }

    assert humidity_of(Sensor(entity="sensor.hall_temperature"), live) == "sensor.hall_humidity"
    assert humidity_of(Sensor(entity="sensor.attic_temperature"), live) is None
    assert humidity_of(Sensor(entity="sensor.attic_temperature", humidity="sensor.attic_humidity"), live) == "sensor.attic_humidity"


def test_the_last_real_change_skips_going_offline_and_back():
    assert last_real_change([(1, "off"), (2, "on"), (3, "off"), (4, "unavailable"), (5, "off")]) == 3
    assert last_real_change([(1, "closed"), (2, "opening"), (3, "open"), (4, "unknown"), (5, "open")]) == 2
    assert last_real_change([(1, "off"), (2, "unavailable"), (3, "on")]) == 3
    assert last_real_change([(1, "unavailable")]) is None
