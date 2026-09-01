// All server configuration, overridable by environment variable.

// 'metric' (Celsius, 24-hour clock) or 'imperial' (Fahrenheit, 12-hour clock).
const unitSystem = (process.env.HF_UNITS ?? 'metric').toLowerCase() === 'imperial'
  ? 'imperial'
  : 'metric';
const metric = unitSystem === 'metric';

export const config = {
  port: Number(process.env.HF_PORT ?? 8080),

  // Bind address. Default to the IPv4 wildcard rather than Node's IPv6
  // wildcard: the device connects over IPv4, and v4-mapped acceptance on
  // a dual-stack socket is not worth relying on.
  host: process.env.HF_HOST ?? '0.0.0.0',

  // Native panel geometry. The device always receives 960x680 scanlines.
  panel: { width: 960, height: 680 },

  // 'landscape' renders the page at 960x680 directly.
  // 'portrait' renders at 680x960 and rotates into the native orientation, for
  // a frame hung the tall way. Must agree with HF_DISPLAY_ROTATION in the
  // firmware, which only affects the on-device fallback screen.
  orientation: process.env.HF_ORIENTATION ?? 'landscape',

  // Greyscale cutoff, 0-255. Text stays crisp with a hard threshold; turn on
  // dithering only when the dashboard carries photos.
  threshold: Number(process.env.HF_THRESHOLD ?? 160),
  dither: process.env.HF_DITHER === '1',

  // Re-render at most this often, however many devices are polling.
  renderTtlMs: Number(process.env.HF_RENDER_TTL_MS ?? 30_000),

  // Must match HF_SERVER_TOKEN in the firmware. Empty disables the check.
  token: process.env.HF_TOKEN ?? '',

  // Override the browser binary. Falls back to puppeteer's managed download.
  // Also honours PUPPETEER_EXECUTABLE_PATH, which puppeteer reads itself.
  chromePath: process.env.HF_CHROME_PATH ?? '',

  timeZone: process.env.HF_TZ ?? 'America/Los_Angeles',
  locale: process.env.HF_LOCALE ?? 'en-US',

  // Where the frame lives. Used for the weather forecast.
  latitude: Number(process.env.HF_LAT ?? 37.7749),
  longitude: Number(process.env.HF_LON ?? -122.4194),
  locationName: process.env.HF_LOCATION ?? 'San Francisco',

  // Unit system, see `metric` below. Set via HF_UNITS.
  units: unitSystem,

  // Derived from the unit system so the dashboard stays internally consistent:
  // metric implies Celsius and a 24-hour clock, imperial implies Fahrenheit
  // and a 12-hour one.
  temperatureUnit: metric ? 'celsius' : 'fahrenheit',
  hour12: !metric,
};

export const frameBytes = (config.panel.width / 8) * config.panel.height;
