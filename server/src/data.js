// Dashboard data sources.
//
// Each function is a seam where a real source goes. Keep them independent and
// failure-tolerant — one dead upstream should degrade its own panel, not blank
// the whole frame.
import { config } from './config.js';
import { deviceStatus } from './device.js';

// WMO weather codes, as returned by Open-Meteo. Kept short: these render into
// a narrow column on the panel, so anything past ~16 characters will wrap.
const WMO = {
  0: 'Clear', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
  45: 'Fog', 48: 'Freezing fog',
  51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
  56: 'Freezing drizzle', 57: 'Freezing drizzle',
  61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
  66: 'Freezing rain', 67: 'Freezing rain',
  71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains',
  80: 'Light showers', 81: 'Showers', 82: 'Heavy showers',
  85: 'Snow showers', 86: 'Snow showers',
  95: 'Thunderstorm', 96: 'Thunderstorm', 99: 'Thunderstorm',
};

const describe = (code) => WMO[code] ?? 'Unknown';

// The forecast cards are ~100px wide. Anything longer than about nine
// characters wraps and pushes the column past the panel height, so the strip
// gets its own coarser vocabulary.
const WMO_SHORT = {
  0: 'Clear', 1: 'Clear', 2: 'Cloudy', 3: 'Overcast',
  45: 'Fog', 48: 'Fog',
  51: 'Drizzle', 53: 'Drizzle', 55: 'Drizzle', 56: 'Drizzle', 57: 'Drizzle',
  61: 'Rain', 63: 'Rain', 65: 'Rain', 66: 'Rain', 67: 'Rain',
  71: 'Snow', 73: 'Snow', 75: 'Snow', 77: 'Snow',
  80: 'Showers', 81: 'Showers', 82: 'Showers',
  85: 'Snow', 86: 'Snow',
  95: 'Storm', 96: 'Storm', 99: 'Storm',
};

const describeShort = (code) => WMO_SHORT[code] ?? '';

// Open-Meteo's daily.time entries are bare "YYYY-MM-DD" strings. Parsing one
// directly yields UTC midnight, which formats to the *previous* day in any
// negative-offset zone — so pin it to UTC on both ends.
function weekdayLabel(isoDate) {
  return new Intl.DateTimeFormat(config.locale, {
    weekday: 'short', timeZone: 'UTC',
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

// Open-Meteo is free and needs no API key, but there is no reason to hit it on
// every render — the forecast does not change every 30 seconds.
let weatherCache = null;
const WEATHER_TTL_MS = 10 * 60 * 1000;

async function weather() {
  if (weatherCache && Date.now() - weatherCache.at < WEATHER_TTL_MS) {
    return weatherCache.value;
  }

  const url = new URL('https://api.open-meteo.com/v1/forecast');
  url.search = new URLSearchParams({
    latitude: config.latitude,
    longitude: config.longitude,
    current: 'temperature_2m,weather_code',
    daily: 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
    timezone: config.timeZone,
    temperature_unit: config.temperatureUnit,
    forecast_days: '4',
  });

  const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`open-meteo ${res.status}`);
  const d = await res.json();

  const value = {
    location: config.locationName,
    now: {
      temp: d.current.temperature_2m,
      summary: describe(d.current.weather_code),
    },
    today: {
      high: d.daily.temperature_2m_max[0],
      low: d.daily.temperature_2m_min[0],
      precipitation: d.daily.precipitation_probability_max[0] ?? 0,
    },
    // Today is already shown above, so the strip covers the next three days.
    forecast: [1, 2, 3].map((i) => ({
      day: weekdayLabel(d.daily.time[i]),
      high: d.daily.temperature_2m_max[i],
      low: d.daily.temperature_2m_min[i],
      summary: describeShort(d.daily.weather_code[i]),
    })),
  };

  weatherCache = { at: Date.now(), value };
  return value;
}

async function agenda() {
  // TODO: replace with CalDAV / Google Calendar / Home Assistant calendar.
  return [
    { time: '09:00', title: 'Standup', who: 'Sascha' },
    { time: '13:30', title: 'Dentist', who: 'Family' },
    { time: '18:00', title: 'Football practice', who: 'Kids' },
  ];
}

async function notes() {
  // TODO: replace with a shared list (Home Assistant to-do, Todoist, a file).
  return ['Bins out tonight', 'Order more coffee'];
}

// Settles every source independently so a single failure cannot take the
// dashboard down; failed panels come back as null and the page hides them.
export async function collect() {
  const [w, a, n] = await Promise.allSettled([weather(), agenda(), notes()]);
  const value = (r) => {
    if (r.status === 'fulfilled') return r.value;
    console.warn('data source failed:', r.reason?.message ?? r.reason);
    return null;
  };

  const now = new Date();
  return {
    generatedAt: now.toISOString(),
    clock: new Intl.DateTimeFormat(config.locale, {
      hour: '2-digit', minute: '2-digit', hour12: config.hour12, timeZone: config.timeZone,
    }).format(now),
    date: new Intl.DateTimeFormat(config.locale, {
      weekday: 'long', day: 'numeric', month: 'long', timeZone: config.timeZone,
    }).format(now),
    weather: value(w),
    agenda: value(a),
    notes: value(n),
    device: deviceStatus(),
  };
}
