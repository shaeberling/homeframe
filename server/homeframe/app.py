"""homeframe server: one core on top of Home Assistant, shown two ways.

    python -m homeframe            # uses config.yaml
    python -m homeframe --demo     # synthetic data, no Home Assistant needed

The web dashboard at / is the live view of every house. The e-paper frame
fetches /frame.bin, a headless render of /frame packed for its panel.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, ConfigError, load_config
from .demo import demo_config
from .frame.device import record_telemetry
from .frame.pack import FRAME_BYTES, PANEL_HEIGHT, PANEL_WIDTH, Packed
from .frame.render import Renderer
from .frame.still import StillError, list_images, pack_still
from .frame.view import frame_view
from .hub import Hub

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

log = logging.getLogger("homeframe")

STREAM_KEEPALIVE = 20


class NoCacheStatic(StaticFiles):
    """Static files that always revalidate, so UI edits show up on reload."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def frame_response(request: Request, packed: Packed) -> Response:
    """The packed frame, or 304 when the device already shows it."""
    headers = {"ETag": packed.etag, "Cache-Control": "no-cache"}
    if request.headers.get("If-None-Match") == packed.etag:
        return Response(status_code=304, headers=headers)
    return Response(packed.frame, media_type="application/octet-stream", headers=headers)


def create_app(config: Config, port: int) -> FastAPI:
    hub = Hub(config)
    # The renderer is a browser on this machine, whatever address we listen on.
    loopback = config.host if config.host not in ("0.0.0.0", "::", "") else "127.0.0.1"
    renderer = Renderer(config.frame, f"http://{loopback}:{port}/frame")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await hub.start()
        yield
        await renderer.close()
        await hub.stop()

    app = FastAPI(title="homeframe", lifespan=lifespan, docs_url=None, redoc_url=None)

    # --- web dashboard ------------------------------------------------------

    @app.get("/api/dashboard")
    async def dashboard():
        return hub.dashboard()

    @app.get("/api/history")
    async def history(hours: int = Query(24, ge=1, le=24 * 31)):
        return await hub.history(hours)

    @app.get("/api/events")
    async def events(instance: str, entity: str):
        result = await hub.events(instance, entity)
        if result is None:
            raise HTTPException(404, "Not a door or motion sensor on this dashboard")
        return result

    # Server-sent events: one "change" the moment a door or motion sensor
    # changes, so the browser refreshes then instead of on its next poll.
    @app.get("/api/stream")
    async def stream():
        async def events():
            watcher = hub.watch()
            try:
                yield "retry: 3000\n\n"
                while not hub.closing:
                    try:
                        await asyncio.wait_for(watcher.wait(), STREAM_KEEPALIVE)
                    except TimeoutError:
                        yield ": keep-alive\n\n"  # so proxies and the browser keep the stream open
                        continue
                    watcher.clear()
                    yield "event: change\ndata: {}\n\n"
            finally:
                hub.unwatch(watcher)

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    # --- e-paper frame ------------------------------------------------------

    @app.get("/api/frame")
    async def frame_data():
        return frame_view(hub)

    @app.get("/frame")
    async def frame_page():
        return FileResponse(WEB / "frame" / "index.html", headers={"Cache-Control": "no-cache"})

    async def render(fresh: bool) -> Packed:
        try:
            return await renderer.get(fresh)
        except Exception as error:
            log.exception("frame render failed")
            raise HTTPException(500, f"render failed: {error}") from error

    # What the panel fetches: 81600 raw bytes, or 304 when nothing changed.
    @app.get("/frame.bin")
    async def frame_bin(request: Request, fresh: str | None = None):
        # Shared secret, if configured. The page and preview stay open so the
        # design can be iterated on in a browser.
        if config.frame.token and request.headers.get("X-Homeframe-Token") != config.frame.token:
            return PlainTextResponse("bad or missing X-Homeframe-Token\n", status_code=401)
        # Before rendering, so this frame carries the device's current numbers.
        record_telemetry(request.headers)
        return frame_response(request, await render(fresh is not None))

    # The same render as a PNG: the fast way to iterate on the design without
    # touching hardware.
    @app.get("/preview.png")
    async def preview(fresh: str | None = None):
        return Response((await render(fresh is not None)).png, media_type="image/png")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "width": PANEL_WIDTH, "height": PANEL_HEIGHT}

    # --- still images -------------------------------------------------------
    # Registered after /frame.bin and /preview.png so those keep their
    # handlers. Any server/images/<name>.png is served packed at /<name>.bin
    # and previewed at /<name>.png. Both accept ?dither=1 and ?threshold=N.

    @app.get("/images")
    async def images():
        return {"images": list_images(), "dir": "server/images"}

    async def still(name: str, dither: str | None, threshold: int | None) -> Packed:
        try:
            return await asyncio.to_thread(
                pack_still, name,
                config.frame.threshold if threshold is None else threshold,
                config.frame.dither if dither is None else dither != "0",
            )
        except StillError as error:
            raise HTTPException(error.status, str(error)) from error

    @app.get("/{name:str}.bin")
    async def still_bin(request: Request, name: str, dither: str | None = None, threshold: int | None = None):
        return frame_response(request, await still(name, dither, threshold))

    @app.get("/{name:str}.png")
    async def still_png(name: str, dither: str | None = None, threshold: int | None = None):
        return Response((await still(name, dither, threshold)).png, media_type="image/png")

    app.mount("/", NoCacheStatic(directory=WEB / "dashboard", html=True), name="static")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(prog="homeframe", description="homeframe server")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml", help="path to config.yaml")
    parser.add_argument("--demo", action="store_true", help="run with synthetic data instead of Home Assistant")
    parser.add_argument("--host", help="override server.host from the config")
    parser.add_argument("--port", type=int, help="override server.port from the config")
    args = parser.parse_args()

    if args.demo:
        config = demo_config()
    elif not args.config.exists():
        sys.exit(
            f"No config found at {args.config}.\n"
            "Copy config.example.yaml to config.yaml and add your Home Assistant instances,\n"
            "or run with --demo to try both displays with synthetic data."
        )
    else:
        try:
            config = load_config(args.config)
        except ConfigError as error:
            sys.exit(f"Config error: {error}")

    config.host = args.host or config.host
    port = args.port or config.port

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    # One line per request from the polling UI would drown everything else.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(f"homeframe{' (demo data)' if config.demo else ''} on http://localhost:{port} (bound {config.host})")
    print("  dashboard  /             (the live web dashboard)")
    print("  frame      /frame        (edit web/frame/index.html, reload)")
    print("  preview    /preview.png  (exactly what the panel will show)")
    print(f"  device     /frame.bin    ({FRAME_BYTES} bytes, {config.frame.orientation})")
    # Browser streams stay open for hours; do not wait for them when stopping.
    uvicorn.run(create_app(config, port), host=config.host, port=port, log_level="warning", timeout_graceful_shutdown=3)
