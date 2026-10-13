from homeframe.weather import sun_times


def sun(rising, setting):
    return {"sun.sun": {"state": "above_horizon", "attributes": {"next_rising": rising, "next_setting": setting}}}


def test_sun_times_are_minutes_into_the_local_day():
    states = sun("2026-10-13T05:30:00+00:00", "2026-10-12T16:45:00+00:00")
    assert sun_times(states, "Europe/Paris") == {"rise": 7 * 60 + 30, "set": 18 * 60 + 45}
    assert sun_times(states, None) == {"rise": 5 * 60 + 30, "set": 16 * 60 + 45}


def test_no_sun_entity_means_no_sun_times():
    assert sun_times({}, "Europe/Paris") is None
    assert sun_times(sun(None, "2026-10-12T16:45:00+00:00"), "Europe/Paris") is None
