import asyncio

import pytest

from homeframe.config import ConfigError, Screen, _screen
from homeframe.screen import ScreenSwitch, output_names

LISTING = "HDMI-A-1 on\nHDMI-A-2 off\n"


def recorder(fail=False):
    calls = []

    async def run(*args):
        calls.append(args)
        if fail:
            raise RuntimeError("no compositor")
        return LISTING if not args else ""

    return run, calls


def test_the_screen_follows_the_entity_and_switches_only_on_a_change():
    async def go():
        run, calls = recorder()
        screen = ScreenSwitch(Screen(entity="input_boolean.screen", instance="home"), run)
        await screen.follow({"state": "off"})
        await screen.follow({"state": "off"})        # already off
        await screen.follow({"state": "unavailable"})  # tells nothing
        await screen.follow(None)
        await screen.follow({"state": "on"})
        return calls

    assert asyncio.run(go()) == [
        (), ("--off", "HDMI-A-1"), ("--off", "HDMI-A-2"),
        (), ("--on", "HDMI-A-1"), ("--on", "HDMI-A-2"),
    ]


def test_named_outputs_are_switched_alone_and_a_failure_is_tried_again():
    async def go():
        run, calls = recorder(fail=True)
        screen = ScreenSwitch(Screen(entity="switch.screen", instance="home", outputs=["HDMI-A-1"]), run)
        await screen.follow({"state": "off"})
        await screen.follow({"state": "off"})
        return calls

    assert asyncio.run(go()) == [("--off", "HDMI-A-1")] * 2


def test_output_names_come_from_the_listing():
    assert output_names(LISTING) == ["HDMI-A-1", "HDMI-A-2"]


def test_the_screen_config_defaults_to_the_home_instance():
    assert _screen({}, ["home"], "home") is None
    assert _screen({"entity": "input_boolean.screen", "output": "HDMI-A-1"}, ["home", "cabin"], "home") == Screen(
        "input_boolean.screen", "home", ["HDMI-A-1"],
    )
    with pytest.raises(ConfigError):
        _screen({"instance": "home"}, ["home"], "home")
