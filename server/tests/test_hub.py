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


class Recorded:
    """A client whose history says the door last closed at 1000, before a restart at 5000."""

    def __init__(self):
        self.asked = 0

    async def state_changes(self, entity_id, start, end):
        self.asked += 1
        return [(500.0, "on"), (1000.0, "off"), (5000.0, "unavailable"), (5001.0, "off")]


def test_a_restart_of_home_assistant_does_not_count_as_a_door_change():
    async def run():
        hub = Hub(demo_config())
        home = hub.config.instance("home")
        live = hub.live("home")
        restarted = "1970-01-01T01:23:21+00:00"  # 5001 seconds
        live.last_ok = 1.0
        live.states = {"binary_sensor.front_door": {**state("binary_sensor.front_door", "off", restarted), "last_changed": restarted}}
        client = hub._clients["home"] = Recorded()

        await hub._refresh_activity_times(home)
        item = next(i for p in hub.dashboard()["activity"] for i in p["items"] if i["entity"] == "binary_sensor.front_door")
        assert item["since"] == 1000.0

        await hub._refresh_activity_times(home)
        assert client.asked == 1  # once per change, not once per poll

    asyncio.run(run())


class Purged:
    """A client whose history only reaches back to a restart at 5000."""

    async def state_changes(self, entity_id, start, end):
        return [(5000.0, "unavailable"), (5001.0, "off")]


def test_what_was_seen_before_a_restart_outlasts_the_purged_history():
    async def run():
        hub = Hub(demo_config())
        home = hub.config.instance("home")
        live = hub.live("home")
        restarted = "1970-01-01T01:23:21+00:00"  # 5001 seconds
        live.last_ok = 1.0
        live.states = {"binary_sensor.front_door": {**state("binary_sensor.front_door", "off", restarted), "last_changed": restarted}}
        live.changed["binary_sensor.front_door"] = ("before the restart", 1000.0, "off")
        hub._clients["home"] = Purged()

        await hub._refresh_activity_times(home)
        assert live.changed["binary_sensor.front_door"][1] == 1000.0

        # Without anything seen before, the restart is the best there is.
        live.changed.clear()
        await hub._refresh_activity_times(home)
        assert live.changed["binary_sensor.front_door"][1] == 5001.0

    asyncio.run(run())
