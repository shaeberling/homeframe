"""The monitor the dashboard is shown on, switched by a Home Assistant entity.

While the entity is off, the monitor is put to standby (DPMS); when it turns
on again, the monitor wakes up. The output stays configured meanwhile, so
windows keep their place. This works under a wlroots compositor such as labwc
(the Raspberry Pi desktop), through wlopm.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .config import Screen

log = logging.getLogger("homeframe")

WANTED = {"on": True, "off": False}


async def wlopm(*args: str) -> str:
    # A system service doesn't inherit the desktop session's variables.
    env = {"WAYLAND_DISPLAY": "wayland-0", **os.environ}
    process = await asyncio.create_subprocess_exec(
        "wlopm", *args, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await process.communicate()
    if process.returncode:
        raise RuntimeError(err.decode().strip() or f"wlopm exited with {process.returncode}")
    return out.decode()


def output_names(listing: str) -> list[str]:
    """The outputs in what wlopm prints: one "NAME on|off" line each."""
    return [line.split()[0] for line in listing.splitlines() if line.strip()]


class ScreenSwitch:
    def __init__(self, setting: Screen, run=wlopm):
        self.setting = setting
        self._run = run
        self._lock = asyncio.Lock()
        # What was last set; None until the entity has been seen once.
        self._applied: bool | None = None
        self._error: str | None = None

    async def follow(self, state: dict | None) -> None:
        """Switch the outputs to match the entity; unknown states change nothing."""
        wanted = WANTED.get((state or {}).get("state"))
        async with self._lock:
            if wanted is None or wanted == self._applied:
                return
            try:
                outputs = self.setting.outputs or output_names(await self._run())
                for output in outputs:
                    await self._run("--on" if wanted else "--off", output)
            except Exception as error:  # tried again on the next poll
                if str(error) != self._error:
                    log.warning("screen: could not switch %s: %s", "on" if wanted else "off", error)
                self._error = str(error)
                return
            self._applied, self._error = wanted, None
            log.info("screen: %s", "on" if wanted else "standby")
