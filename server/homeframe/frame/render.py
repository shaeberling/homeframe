"""Headless render of the frame page into a packed 1bpp frame."""

from __future__ import annotations

import asyncio
import io
import shutil
import time

from PIL import Image
from playwright.async_api import async_playwright

from ..config import Frame
from .pack import PANEL_HEIGHT, PANEL_WIDTH, Packed, pack_image

SYSTEM_BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


class Renderer:
    def __init__(self, frame: Frame, url: str):
        self.frame = frame
        self.url = url
        self._portrait = frame.orientation == "portrait"
        self._playwright = None
        self._browser = None
        self._in_flight: asyncio.Task | None = None
        self._cached: Packed | None = None
        self._rendered_at = 0.0

    async def get(self, fresh: bool = False) -> Packed:
        """Serves from cache within the TTL, and collapses concurrent requests onto a single browser render."""
        if not fresh and self._cached and time.monotonic() - self._rendered_at < self.frame.render_ttl:
            return self._cached
        if not self._in_flight:
            self._in_flight = asyncio.create_task(self._render())
            self._in_flight.add_done_callback(lambda _task: setattr(self, "_in_flight", None))
        # Shielded: one requester giving up must not cancel the render for the rest.
        return await asyncio.shield(self._in_flight)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = self._playwright = None

    async def _launch(self):
        if self._browser and self._browser.is_connected():
            return self._browser
        if not self._playwright:
            self._playwright = await async_playwright().start()
        # A system Chromium saves Playwright's own download; on a Raspberry Pi
        # it is also the build that is known to run.
        path = self.frame.chrome_path or next(filter(None, map(shutil.which, SYSTEM_BROWSERS)), None)
        self._browser = await self._playwright.chromium.launch(
            executable_path=path,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--force-device-scale-factor=1"],
        )
        return self._browser

    async def _screenshot(self) -> bytes:
        # The page is laid out in the mounted orientation, then rotated into
        # the panel's native scanline order.
        width, height = (PANEL_HEIGHT, PANEL_WIDTH) if self._portrait else (PANEL_WIDTH, PANEL_HEIGHT)
        browser = await self._launch()
        page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        try:
            await page.goto(self.url, wait_until="networkidle", timeout=30_000)
            # frame/index.html sets this once it has painted its data.
            await page.wait_for_function("window.__hfReady === true", timeout=15_000)
            return await page.screenshot(type="png")
        finally:
            await page.close()

    async def _render(self) -> Packed:
        png = await self._screenshot()
        packed = await asyncio.to_thread(self._pack, png)
        self._cached, self._rendered_at = packed, time.monotonic()
        return packed

    def _pack(self, png: bytes) -> Packed:
        image = Image.open(io.BytesIO(png))
        if self._portrait:
            image = image.transpose(Image.Transpose.ROTATE_270)
        return pack_image(image, self.frame.threshold, self.frame.dither)
