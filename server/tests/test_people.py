from types import SimpleNamespace

from homeframe.config import Config, Instance, Person, Place
from homeframe.people import distance, people_view

HOME = {"entity_id": "zone.home", "state": "1", "attributes": {"latitude": 50.0, "longitude": 8.0, "radius": 100}}


def view(person_state, *others, places=(), address=None):
    config = Config(
        instances=[Instance(id="home", name="Home", url="http://ha", token="t")],
        people=[Person("person.sam", "", address=address)],
        places=list(places),
    )
    states = {s["entity_id"]: s for s in (HOME, person_state, *others)}
    return people_view(config, {"home": SimpleNamespace(states=states)})[0]


def person(state, latitude=None, longitude=None, **attrs):
    attributes = {"friendly_name": "Sam", "source": "device_tracker.sam_phone", **attrs}
    if latitude is not None:
        attributes.update(latitude=latitude, longitude=longitude)
    return {"entity_id": "person.sam", "state": state, "attributes": attributes, "last_updated": "2026-10-12T10:00:00+00:00"}


def geocoded(**attrs):
    return {"entity_id": "sensor.sam_phone_geocoded_location", "state": "1 Main St, Springfield", "attributes": attrs}


def test_distance_is_in_metres():
    assert 110_000 < distance(50.0, 8.0, 51.0, 8.0) < 112_500
    assert distance(50.0, 8.0, 50.0, 8.0) == 0


def test_at_home_and_in_another_home_assistant_zone():
    assert view(person("home", 50.0, 8.0))["where"] == "Home"
    office = view(person("Office", 50.2, 8.2))
    assert (office["kind"], office["where"]) == ("place", "Office")


def test_within_the_radius_of_a_known_place_the_nearest_wins():
    places = [Place("School", 50.1, 8.1, 200), Place("Playground", 50.1009, 8.1, 200)]
    result = view(person("not_home", 50.1008, 8.1), geocoded(Thoroughfare="Main St", Locality="Springfield"), places=places)
    assert (result["kind"], result["where"]) == ("place", "Playground")


def test_a_place_can_belong_to_some_people_only():
    at_work = person("not_home", 50.1, 8.1)
    theirs = [Place("Their office", 50.1, 8.1, 200, people=["person.kim"])]
    assert view(at_work, places=theirs)["kind"] == "away"
    mine = [Place("My office", 50.1, 8.1, 200, people=["person.sam"])]
    assert view(at_work, places=mine)["where"] == "My office"


def test_outside_every_place_the_phones_address_is_used():
    places = [Place("School", 50.1, 8.1, 200)]
    android = view(person("not_home", 50.3, 8.3), geocoded(Thoroughfare="Main St", Locality="Springfield"), places=places)
    assert (android["kind"], android["where"]) == ("address", "Main St · Springfield")
    lower = view(person("not_home", 50.3, 8.3), geocoded(thoroughfare="Main St", locality="N/A", sub_locality="Old Town"))
    assert lower["where"] == "Main St · Old Town"
    bare = view(person("not_home", 50.3, 8.3), geocoded())
    assert bare["where"] == "1 Main St · Springfield"


def test_without_an_address_the_distance_from_home_has_to_do():
    assert view(person("not_home", 50.0, 8.05))["where"] == "3.6 km from home"
    unavailable = {**geocoded(), "state": "unavailable"}
    assert view(person("not_home", 51.0, 8.0), unavailable)["where"] == "111 km from home"


def test_no_position_at_all():
    assert view(person("not_home"))["where"] == "Away"
    assert view(person("unknown"))["kind"] == "unknown"
    assert view(person("home"))["updated"] == 1791799200.0
