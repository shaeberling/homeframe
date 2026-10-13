from types import SimpleNamespace

from homeframe.config import Instance, Lights
from homeframe.lights import light_entities, lights_view


def entity(entity_id, state, name, **attrs):
    return {"entity_id": entity_id, "state": state, "attributes": {"friendly_name": name, **attrs}}


STATES = {s["entity_id"]: s for s in [
    entity("light.kitchen_shelves", "on", "Kitchen Shelves", brightness=128),
    entity("light.kitchen_island", "off", "Kitchen Island"),
    entity("light.bedroom_main", "off", "Bedroom Main Lights"),
    entity("light.garage_1", "unavailable", "Garage 1 Light"),
    entity("light.status_led", "on", "Status LED"),
    entity("switch.desk_lamp", "on", "Desk Lamp"),
    entity("switch.pump", "on", "Pump"),
]}
ROOMS = {
    "light.kitchen_shelves": {"room": "Kitchen", "floor": "1st floor", "level": 1},
    "light.kitchen_island": {"room": "Kitchen", "floor": "1st floor", "level": 1},
    "light.bedroom_main": {"room": "Bedroom", "floor": "2nd floor", "level": 2},
    "light.garage_1": {"room": "Garage", "floor": "Ground floor", "level": 0},
    "switch.desk_lamp": {"room": "Office", "floor": None, "level": None},
}


def house(lights):
    return Instance(id="home", name="Home", url="http://ha", token="t", lights=lights)


def view(lights):
    return lights_view(house(lights), SimpleNamespace(states=STATES, rooms=ROOMS, status="online"))


def test_every_light_unless_excluded_plus_what_is_included():
    assert len(light_entities(house(Lights()), STATES)) == 5
    chosen = light_entities(house(Lights(exclude=["light.status_*"], include=["switch.desk_lamp"])), STATES)
    assert "light.status_led" not in chosen and "switch.desk_lamp" in chosen and "switch.pump" not in chosen
    assert light_entities(house(None), STATES) == []


def test_floors_from_the_top_down_then_what_has_no_floor():
    panel = view(Lights(exclude=["light.status_*"], include=["switch.desk_lamp"]))
    assert [f["name"] for f in panel["floors"]] == ["2nd floor", "1st floor", "Ground floor", None]
    assert (panel["on"], panel["total"]) == (2, 5)


def test_names_lose_their_room_and_brightness_is_a_percentage():
    kitchen = next(f for f in view(Lights())["floors"] if f["name"] == "1st floor")["rooms"][0]
    assert kitchen["name"] == "Kitchen"
    assert [(l["name"], l["status"], l["brightness"]) for l in kitchen["lights"]] == [("Island", "off", None), ("Shelves", "on", 50)]
    garage = next(f for f in view(Lights())["floors"] if f["name"] == "Ground floor")["rooms"][0]["lights"][0]
    assert (garage["name"], garage["status"]) == ("Garage 1", "offline")


def test_a_light_is_not_called_light_unless_that_is_all_it_is_called():
    from homeframe.lights import _short
    assert _short("Bedroom Main Lights", "Bedroom") == "Main"
    assert _short("Garden Lights", "Garden") == "Lights"
    assert _short("Hall Light", None) == "Hall"
    assert _short("Desk Lamp", "Office") == "Desk Lamp"


def test_a_light_that_is_on_reports_its_colour_when_it_has_one():
    states = {s["entity_id"]: s for s in [
        entity("light.blue", "on", "Blue", rgb_color=[0, 0, 255]),
        entity("light.dimmer", "on", "Dimmer", brightness=255),
        entity("light.was_red", "off", "Was red", rgb_color=[255, 0, 0]),
        entity("light.odd", "on", "Odd", rgb_color="blue"),
    ]}
    panel = lights_view(house(Lights()), SimpleNamespace(states=states, rooms={}, status="online"))
    colors = {l["full_name"]: l["color"] for l in panel["floors"][0]["rooms"][0]["lights"]}
    assert colors == {"Blue": [0, 0, 255], "Dimmer": None, "Was red": None, "Odd": None}


def test_lights_without_a_room_come_after_the_rooms():
    elsewhere = view(Lights())["floors"][-1]
    assert elsewhere["name"] is None and elsewhere["rooms"][-1]["name"] is None
    assert elsewhere["rooms"][-1]["lights"][0]["name"] == "Status LED"
