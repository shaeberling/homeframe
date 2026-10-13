import asyncio

from homeframe.demo import demo_config
from homeframe.hub import Hub, merge_states


def state(entity, value, updated):
    return {"entity_id": entity, "state": value, "last_updated": updated}


def test_poll_does_not_undo_a_newer_pushed_change():
    held = {"binary_sensor.door": state("binary_sensor.door", "on", "2026-10-12T10:00:05+00:00")}
    polled = [
        state("binary_sensor.door", "off", "2026-10-12T10:00:01+00:00"),
        state("sensor.temp", "20", "2026-10-12T10:00:00+00:00"),
    ]
    merged = merge_states(held, polled)
    assert merged["binary_sensor.door"]["state"] == "on"
    assert merged["sensor.temp"]["state"] == "20"


def test_poll_wins_when_it_is_newer_and_drops_what_is_gone():
    held = {
        "binary_sensor.door": state("binary_sensor.door", "on", "2026-10-12T10:00:00+00:00"),
        "sensor.removed": state("sensor.removed", "1", "2026-10-12T10:00:09+00:00"),
    }
    merged = merge_states(held, [state("binary_sensor.door", "off", "2026-10-12T10:00:03+00:00")])
    assert merged == {"binary_sensor.door": state("binary_sensor.door", "off", "2026-10-12T10:00:03+00:00")}


def test_pushed_door_change_wakes_the_browsers_but_a_temperature_does_not():
    async def run():
        hub = Hub(demo_config())
        home = hub.config.instance("home")
        live = hub.live("home")
        live.last_ok = 1.0
        live.states = {"binary_sensor.front_door": state("binary_sensor.front_door", "off", "a")}
        watcher = hub.watch()

        hub._apply(home, "sensor.kitchen_temperature", state("sensor.kitchen_temperature", "21", "b"))
        assert not watcher.is_set() and live.states["sensor.kitchen_temperature"]["state"] == "21"

        hub._apply(home, "binary_sensor.front_door", state("binary_sensor.front_door", "off", "c"))
        assert not watcher.is_set()  # same state, only an attribute update

        hub._apply(home, "binary_sensor.front_door", state("binary_sensor.front_door", "on", "d"))
        assert watcher.is_set() and live.states["binary_sensor.front_door"]["state"] == "on"

    asyncio.run(run())


def test_pushed_changes_wait_for_the_first_poll():
    async def run():
        hub = Hub(demo_config())
        hub._apply(hub.config.instance("home"), "binary_sensor.front_door", state("binary_sensor.front_door", "on", "a"))
        assert hub.live("home").states == {}

    asyncio.run(run())
