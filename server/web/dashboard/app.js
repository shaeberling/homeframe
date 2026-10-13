const POLL_MS = 5000;
const HISTORY_REFRESH_MS = 120000;
const RANGES = [
  { hours: 6, label: '6H' },
  { hours: 24, label: '24H' },
  { hours: 168, label: '7D' },
  { hours: 720, label: '30D' },
];
// The sensor overlay looks further back; six hours is too short to be worth a button there.
const DETAIL_RANGES = RANGES.filter((range) => range.hours >= 24);
const STATUS_LABEL = { ok: 'Nominal', low: 'Low', critical: 'Critical', offline: 'Offline', nodata: 'No data' };
const KIND_LABEL = { offline: 'Offline', battery: 'Battery', temperature: 'Temperature', instance: 'Instance down' };
const ICONS = {
  offline: '<path d="M2 8.8a15 15 0 0 1 20 0"/><path d="M5 12.5a10.5 10.5 0 0 1 14 0"/><path d="M8.5 16a6 6 0 0 1 7 0"/><path d="M12 19.5h.01"/><path d="M3 3l18 18"/>',
  battery: '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3"/><path d="M5.5 10.5v3"/>',
  temperature: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/><path d="M12 11v6"/>',
  instance: '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  clear: '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
};

// Home Assistant weather conditions → icon + label.
const CLOUD = 'M7 18.5a4 4 0 0 1-.6-7.95 5.5 5.5 0 0 1 10.7-.95A4.5 4.5 0 0 1 17 18.5z';
const CLOUD_HIGH = 'M7 15a3.5 3.5 0 0 1-.5-6.96 5 5 0 0 1 9.7-.84A4 4 0 0 1 16.5 15z';
const RAYS = '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const WEATHER_ICONS = {
  sunny: `<circle cx="12" cy="12" r="4"/>${RAYS}`,
  'clear-night': '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  partlycloudy: '<circle cx="8" cy="8" r="3"/><path d="M8 2v1.5M2 8h1.5M3.8 3.8l1 1M12.2 3.8l-1 1"/><path class="occlude" d="M9 20a3.5 3.5 0 0 1-.5-6.96 5 5 0 0 1 9.7-.84A4 4 0 0 1 18.5 20z"/>',
  cloudy: `<path d="${CLOUD}"/>`,
  fog: `<path d="${CLOUD_HIGH}"/><path d="M5 18.5h14M7.5 21.5h9"/>`,
  rainy: `<path d="${CLOUD_HIGH}"/><path d="M8.5 18l-1 2.5M12.5 18l-1 2.5M16.5 18l-1 2.5"/>`,
  pouring: `<path d="${CLOUD_HIGH}"/><path d="M8.5 17.5l-1.6 4.5M12.5 17.5l-1.6 4.5M16.5 17.5l-1.6 4.5"/>`,
  snowy: `<path d="${CLOUD_HIGH}"/><path d="M8 18.5h.01M12 18.5h.01M16 18.5h.01M10 21.5h.01M14 21.5h.01"/>`,
  'snowy-rainy': `<path d="${CLOUD_HIGH}"/><path d="M8.5 18l-1 2.5M12 19.5h.01M16.5 18l-1 2.5"/>`,
  hail: `<path d="${CLOUD_HIGH}"/><path d="M8 19h.01M12 21h.01M16 19h.01"/>`,
  lightning: `<path d="${CLOUD_HIGH}"/><path d="M12.5 16.5l-2.5 3.2h3l-2 3"/>`,
  'lightning-rainy': `<path d="${CLOUD_HIGH}"/><path d="M12.5 16.5l-2.5 3.2h3l-2 3M7.5 18l-1 2.5M17.5 18l-1 2.5"/>`,
  windy: '<path d="M3 9h10a2.5 2.5 0 1 0-2.5-2.5M3 13h15a2.5 2.5 0 1 1-2.5 2.5M3 17h7"/>',
  exceptional: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
};
WEATHER_ICONS['windy-variant'] = WEATHER_ICONS.windy;
const WEATHER_LABEL = {
  sunny: 'Sunny', 'clear-night': 'Clear night', partlycloudy: 'Partly cloudy', cloudy: 'Cloudy', fog: 'Fog',
  rainy: 'Rain', pouring: 'Heavy rain', snowy: 'Snow', 'snowy-rainy': 'Sleet', hail: 'Hail',
  lightning: 'Thunderstorm', 'lightning-rainy': 'Thunderstorm with rain', windy: 'Windy', 'windy-variant': 'Windy',
  exceptional: 'Exceptional conditions',
};

const GAUGE = { cx: 100, cy: 96, r: 76, from: 135, sweep: 270 };
const CHART = { height: 210, left: 40, right: 14, top: 14, bottom: 26 };

const state = {
  dash: null,
  history: null,
  hours: loadHours(),
  showCharts: loadFlag('show-charts'),
  structure: null,  // signature of the panel layout currently in the DOM
  attention: null,  // signature of the attention list currently in the DOM
  instances: null,
  weather: null,
  batteries: null,
  lights: null,
  people: null,
  stream: false,
  activity: null,
  detail: null,     // sensor overlay: { key, hours, history }
  receivedAt: Date.now(),  // last answer from the dashboard server (page load until there is one)
  unreachable: false,      // the latest request to the dashboard server failed
};

const $ = (selector, root = document) => root.querySelector(selector);
const tooltip = $('#tooltip');

// The layout is designed for a 1920px-wide viewport. Larger displays (a 4K
// screen at native resolution) get that same layout magnified, so everything
// stays on one screen and readable from a distance.
const DESIGN_WIDTH = 1920;
let scale = 1;

function applyScale() {
  scale = window.innerWidth >= 2400 ? window.innerWidth / DESIGN_WIDTH : 1;
  document.body.style.zoom = scale;
  document.documentElement.style.setProperty('--viewport-height', `${window.innerHeight / scale}px`);
  fitSide();
}

// The side column starts below the top bar (and the banner, when there is
// one); it may only be as tall as what is left of the screen from there.
function fitSide() {
  document.documentElement.style.setProperty('--side-top', `${document.querySelector('.side').offsetTop}px`);
}

// ── DOM helpers ──────────────────────────────────────────────

function setAttrs(node, attrs) {
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
}

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  setAttrs(node, attrs);
  node.append(...children.filter((c) => c != null));
  return node;
}

function s(tag, attrs = {}, ...children) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  setAttrs(node, attrs);
  node.append(...children.filter((c) => c != null));
  return node;
}

function strokeIcon(markup, strokeWidth) {
  const node = s('svg', {
    viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    'stroke-width': strokeWidth, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true',
  });
  node.innerHTML = markup;
  return node;
}

const icon = (name) => strokeIcon(ICONS[name] || ICONS.offline, 1.8);
const weatherIcon = (condition) => strokeIcon(WEATHER_ICONS[condition] || WEATHER_ICONS.cloudy, 1.4);

// ── Formatting ───────────────────────────────────────────────

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
const dateFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

const num = (value, digits = 1) => (value == null ? '—' : value.toFixed(digits));
const withUnit = (value, unit) => (value == null ? '—' : `${num(value)}${unit ? ' ' + unit : ''}`);
const clamp01 = (value) => Math.min(1, Math.max(0, value));

// "12 min", "3 h 05 min", "4 days"; nothing for less than a minute and a half.
function elapsed(seconds) {
  if (seconds < 90) return null;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h ${String(minutes % 60).padStart(2, '0')} min`;
  return `${Math.floor(hours / 24)} days`;
}

const duration = (seconds) => { const span = elapsed(seconds); return span ? `for ${span}` : 'just now'; };
const ago = (seconds) => { const span = elapsed(seconds); return span ? `${span} ago` : 'just now'; };

function loadHours() {
  try {
    const saved = Number(localStorage.getItem('history-hours'));
    if (RANGES.some((r) => r.hours === saved)) return saved;
  } catch { /* storage unavailable */ }
  return 24;
}

function loadFlag(name) {
  try { return localStorage.getItem(name) === '1'; } catch { return false; }
}

// ── Top bar ──────────────────────────────────────────────────

function renderRange() {
  const toggle = h('button', { type: 'button', 'aria-pressed': String(state.showCharts), onclick: toggleCharts }, 'Charts');
  const ranges = RANGES.map((range) => h('button', {
    type: 'button',
    'aria-pressed': String(range.hours === state.hours),
    onclick: () => setHours(range.hours),
  }, range.label));
  $('#range').replaceChildren(...ranges, toggle);
}

function toggleCharts() {
  state.showCharts = !state.showCharts;
  try { localStorage.setItem('show-charts', state.showCharts ? '1' : '0'); } catch { /* storage unavailable */ }
  document.body.classList.toggle('charts', state.showCharts);
  renderRange();
  tooltip.hidden = true;
  renderHistory();
}

function setHours(hours) {
  if (hours === state.hours) return;
  state.hours = hours;
  try { localStorage.setItem('history-hours', hours); } catch { /* storage unavailable */ }
  renderRange();
  // Keep the old curves on screen, dimmed, until the new range arrives.
  document.querySelectorAll('.chart').forEach((chart) => chart.classList.add('loading'));
  refreshHistory();
}

// Seconds without a word from the dashboard server, and from an instance's Home Assistant.
const serverSilence = () => (Date.now() - state.receivedAt) / 1000;
const dataAge = (instance) => instance.age + serverSilence();
const staleAfter = () => state.dash?.stale_after ?? 900;
const span = (seconds) => elapsed(seconds) || '1 min';
const forSpan = (seconds) => (seconds < 60 ? '' : ` for ${span(seconds)}`);

function renderInstances(instances) {
  const stale = (instance) => (dataAge(instance) >= staleAfter() ? span(dataAge(instance)) : null);
  const signature = JSON.stringify([state.stream, ...instances.map((i) => [i.id, i.name, i.status, i.error, i.entities, i.push, stale(i)])]);
  if (signature === state.instances) return;
  state.instances = signature;
  // Whether changes are pushed over a connection that is up right now, or
  // only picked up by polling until it is back.
  const link = (live, title) => h('span', { class: 'chip-link', 'data-live': live ? 'yes' : 'no', title }, live ? 'Live' : 'Polling');
  $('#instances').replaceChildren(...instances.map((instance) => {
    const old = stale(instance);
    const sub = old ? `No update for ${old}`
      : { online: `${instance.entities} entities`, error: 'Error', connecting: 'Connecting' }[instance.status];
    return h('div', { class: 'chip', 'data-status': instance.status, 'data-stale': old ? '' : null, title: instance.error || '' },
      h('span', { class: 'chip-dot' }),
      h('span', { class: 'chip-name' }, instance.name),
      h('span', { class: 'chip-sub' }, sub),
      instance.status === 'online' ? link(instance.push, instance.push
        ? `${instance.name} pushes changes to the server as they happen`
        : `The push connection to ${instance.name} is down; the server is polling and reconnecting`) : null);
  }), h('div', { class: 'chip', 'data-status': state.stream ? 'online' : 'connecting' },
    h('span', { class: 'chip-dot' }),
    h('span', { class: 'chip-name' }, 'This screen'),
    link(state.stream, state.stream
      ? 'The server pushes door and motion changes to this screen as they happen'
      : 'The push connection to the server is down; this screen is polling and reconnecting')));
}

// Updates that stopped arriving are easy to miss, since the last values stay on
// screen. Past the limit, the banner and the instance's chip start to pulse.
function renderFreshness() {
  const instances = state.dash?.instances || [];
  const old = instances.filter((instance) => dataAge(instance) >= staleAfter());
  const waiting = state.unreachable || serverSilence() >= staleAfter();
  const stale = serverSilence() >= staleAfter() || old.length > 0;
  const text = !stale
    ? (state.unreachable ? 'Dashboard server not reachable — showing the last known values' : '')
    : waiting
      ? `No update from the dashboard server${forSpan(serverSilence())} — the values shown are old`
      : `No update from ${old.map((i) => `${i.name}${forSpan(dataAge(i))}`).join(' · ')} — the values shown are old`;
  const banner = $('#banner');
  banner.hidden = !text;
  banner.classList.toggle('stale', stale);
  if (banner.textContent !== text) banner.textContent = text;
  renderInstances(instances);
}

function tickClock() {
  const now = new Date();
  $('#clock-time').textContent = now.toLocaleTimeString(undefined, { hour12: false });
  $('#clock-date').textContent = dateFormat.format(now);
  document.querySelectorAll('.wx-local').forEach((node) => {
    node.textContent = timeIn(node.dataset.zone, now);
  });
}

// ── Weather ──────────────────────────────────────────────────

// Each location is shown in its own time zone, which may differ from the browser's.
function timeIn(zone, when) {
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: zone }).format(when);
}

function dayLabel(time, zone) {
  const key = (when) => new Intl.DateTimeFormat('en-CA', { timeZone: zone }).format(when);
  if (key(new Date(time)) === key(new Date())) return 'Today';
  return new Intl.DateTimeFormat(undefined, { weekday: 'short', timeZone: zone }).format(new Date(time));
}

const degrees = (value) => (value == null ? '—' : `${Math.round(value)}°`);

// ── People ───────────────────────────────────────────────────

// "now", "12 min", "3 h", "2 d": when a position was last reported.
function sinceShort(seconds) {
  if (seconds < 90) return 'now';
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

function renderPeople(people) {
  const now = Date.now() / 1000;
  // The ages are relative, so they change when the data doesn't.
  const signature = JSON.stringify(people) + Math.floor(now / 30);
  if (signature === state.people) return;
  state.people = signature;
  const root = $('#people');
  root.hidden = !people.length;
  root.replaceChildren(...people.map((person) => {
    const age = person.updated == null ? null : Math.max(0, now - person.updated);
    const reported = person.updated ? new Date(person.updated * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '';
    return h('div', { class: 'person', 'data-kind': person.kind, title: [person.entity, reported && `position reported ${reported}`].filter(Boolean).join(' · ') },
      h('span', { class: 'person-name' }, person.name),
      h('span', { class: 'person-where' }, person.where),
      h('span', { class: 'person-age' }, age == null ? '' : sinceShort(age) === 'now' ? 'now' : `${sinceShort(age)} ago`));
  }));
}

function renderWeather(locations) {
  const root = $('#weather');
  const signature = JSON.stringify(locations) + new Date().toDateString();
  if (signature === state.weather) return;
  state.weather = signature;
  root.hidden = !locations.length;
  root.replaceChildren(...locations.map((location) => {
    const zone = location.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const details = [
      location.humidity != null && `Humidity ${Math.round(location.humidity)} %`,
      location.wind_speed != null && `Wind ${Math.round(location.wind_speed)} ${location.wind_unit}`,
    ].filter(Boolean).join(' · ');
    const days = location.days.length
      ? h('ol', { class: 'wx-days' }, ...location.days.map((day) => {
        const wet = day.precipitation > 0;
        const rain = wet ? `${num(day.precipitation, day.precipitation < 10 ? 1 : 0)} ${location.precipitation_unit}` : '';
        return h('li', { class: 'wx-day', title: [WEATHER_LABEL[day.condition] || day.condition, rain].filter(Boolean).join(' · ') },
          h('span', { class: 'day' }, dayLabel(day.time, zone), ...(wet ? [h('em', {}, rain)] : [])),
          h('span', { class: 'wx-day-row' },
            weatherIcon(day.condition),
            h('span', { class: 'high' }, degrees(day.high)),
            h('span', { class: 'low' }, degrees(day.low))));
      }))
      : h('p', { class: 'wx-empty' }, 'No forecast available');

    return h('article', { class: `wx frame${location.stale ? ' stale' : ''}`, title: [location.entity, details].filter(Boolean).join('\n') },
      h('div', { class: 'wx-now' },
        weatherIcon(location.condition),
        h('div', {},
          h('div', { class: 'wx-head' },
            h('span', { class: 'tag' }, location.instance),
            h('span', { class: 'label wx-local', 'data-zone': zone, title: 'Local time' }, timeIn(zone, new Date()))),
          h('div', { class: 'wx-line' },
            h('span', { class: 'wx-temp' }, num(location.temperature), h('small', {}, location.unit)),
            h('span', { class: 'wx-condition' }, WEATHER_LABEL[location.condition] || location.condition || 'Unavailable')))),
      days);
  }));
}

// ── Gauge cards ──────────────────────────────────────────────

function gaugePoint(radius, fraction) {
  const angle = ((GAUGE.from + GAUGE.sweep * fraction) * Math.PI) / 180;
  return [GAUGE.cx + radius * Math.cos(angle), GAUGE.cy + radius * Math.sin(angle)];
}

function gaugeArc() {
  const [x0, y0] = gaugePoint(GAUGE.r, 0);
  const [x1, y1] = gaugePoint(GAUGE.r, 1);
  return `M${x0} ${y0}A${GAUGE.r} ${GAUGE.r} 0 1 1 ${x1} ${y1}`;
}

function buildCard(sensor) {
  const ticks = s('g', { class: 'g-ticks' });
  for (let i = 0; i <= 30; i++) {
    const major = i % 5 === 0;
    const [x1, y1] = gaugePoint(GAUGE.r + 9, i / 30);
    const [x2, y2] = gaugePoint(GAUGE.r + (major ? 15 : 12), i / 30);
    ticks.append(s('line', { x1, y1, x2, y2, class: major ? 'major' : null }));
  }
  return h('button', { class: 'card', type: 'button', 'data-key': sensor.key, onclick: () => openDetail(sensor.key) },
    h('span', { class: 'card-head' },
      h('span', { class: 'card-name' }),
      h('span', { class: 'card-status' })),
    s('svg', { class: 'gauge', viewBox: '0 0 200 158', role: 'img' },
      ticks,
      s('path', { class: 'g-track', d: gaugeArc() }),
      s('path', { class: 'g-fill', d: gaugeArc(), pathLength: 100 }),
      s('g', { class: 'g-marks' }),
      s('path', { class: 'spark-area' }),
      s('path', { class: 'spark-line' }),
      s('text', { class: 'g-value', x: 100, y: 100, 'text-anchor': 'middle' }),
      s('text', { class: 'g-unit', x: 100, y: 119, 'text-anchor': 'middle' })),
    h('span', { class: 'card-extra', hidden: true }));
}

function updateCard(card, sensor) {
  const live = sensor.value != null && sensor.status !== 'offline' && sensor.status !== 'nodata';
  const span = sensor.max - sensor.min;
  const fraction = (value) => (value - sensor.min) / span;

  card.dataset.status = sensor.status;
  card.title = sensor.note
    || [sensor.entity, `gauge ${num(sensor.min, 0)}–${num(sensor.max, 0)} ${sensor.unit}`, card.dataset.range].filter(Boolean).join(' · ');
  $('.card-name', card).textContent = sensor.name;
  $('.gauge', card).setAttribute('aria-label', `${sensor.name}: ${withUnit(live ? sensor.value : null, sensor.unit)}, ${STATUS_LABEL[sensor.status]}`);
  $('.g-value', card).textContent = live ? num(sensor.value) : '—';
  $('.g-unit', card).textContent = sensor.unit;
  $('.card-status', card).textContent = STATUS_LABEL[sensor.status];

  const extras = [];
  if (sensor.humidity) {
    const { value, unit } = sensor.humidity;
    extras.push(h('span', {}, 'Humidity', h('b', {}, value == null ? '—' : `${Math.round(value)} ${unit}`)));
  }
  if (sensor.climate) {
    const { mode, target, preset } = sensor.climate;
    const heating = mode && mode !== 'off';
    const setting = !mode ? '—'
      : !heating ? 'Off'
      : target == null ? mode : `${num(target, target % 1 ? 1 : 0)} ${sensor.unit}`;
    // While heating, the preset (comfort, eco, …) stands in for the label.
    extras.push(h('span', { class: heating ? 'active' : null }, (heating && preset) || 'Heating', h('b', {}, setting)));
  }
  const extra = $('.card-extra', card);
  extra.hidden = !extras.length;
  extra.replaceChildren(...extras);

  const fill = $('.g-fill', card);
  fill.style.strokeDasharray = `${live ? clamp01(fraction(sensor.value)) * 100 : 0} 100`;
  fill.style.opacity = live ? 1 : 0;

  const marks = $('.g-marks', card);
  const target = sensor.climate?.mode && sensor.climate.mode !== 'off' ? sensor.climate.target : null;
  const signature = `${sensor.low}|${sensor.critical}|${target}|${sensor.min}|${sensor.max}`;
  if (marks.dataset.signature !== signature) {
    marks.dataset.signature = signature;
    marks.replaceChildren();
    for (const [which, value] of [['low', sensor.low], ['critical', sensor.critical], ['target', target]]) {
      const at = value == null ? -1 : fraction(value);
      if (at <= 0 || at >= 1) continue;
      const [x1, y1] = gaugePoint(GAUGE.r - 8, at);
      const [x2, y2] = gaugePoint(GAUGE.r + 8, at);
      marks.append(s('line', { x1, y1, x2, y2, class: `mark-${which}` }));
    }
  }
}

// The sparkline sits inside the gauge, in the opening at the bottom of the arc.
const SPARK = { left: 55, right: 145, top: 130, bottom: 153 };

function renderSpark(card, points, history) {
  const values = points.map((p) => p[1]).filter((v) => v != null);
  if (!values.length) {
    $('.spark-line', card).setAttribute('d', '');
    $('.spark-area', card).setAttribute('d', '');
    delete card.dataset.range;
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max(0.3, (max - min) * 0.15);
  const x = (t) => SPARK.left + ((t - history.start) / (history.end - history.start)) * (SPARK.right - SPARK.left);
  const y = (v) => SPARK.bottom - ((v - (min - pad)) / (max - min + 2 * pad)) * (SPARK.bottom - SPARK.top);
  const { line, area } = paths(points, x, y, SPARK.bottom + 2);
  $('.spark-line', card).setAttribute('d', line);
  $('.spark-area', card).setAttribute('d', area);
  card.dataset.range = `${RANGES.find((r) => r.hours === history.hours)?.label ?? `${history.hours}H`} low ${num(min)} / high ${num(max)}`;
}

// ── Panels ───────────────────────────────────────────────────

// Cards per row so that rows come out even: 12 sensors → 6 + 6, not 9 + 3.
function gaugeColumns(count) {
  const rows = Math.ceil(count / 9);
  return Math.ceil(count / rows);
}

function buildPanels(panels) {
  const root = $('#panels');
  if (!panels.length) {
    root.replaceChildren(h('p', { class: 'placeholder' }, 'No panels configured'));
    return;
  }
  root.replaceChildren(...panels.map((panel) => {
    const body = panel.sensors.length
      ? [
        h('div', { class: 'gauges', style: `--columns: ${gaugeColumns(panel.sensors.length)}` },
          ...panel.sensors.map(buildCard)),
        h('div', { class: 'chart' },
          h('div', { class: 'chart-head' },
            h('span', { class: 'label' }, 'History'),
            h('span', { class: 'legend' })),
          h('div', { class: 'chart-plot' })),
      ]
      : [h('p', { class: 'placeholder' })];
    // Up to four gauges don't need a full row.
    const small = panel.sensors.length > 0 && panel.sensors.length <= 4;
    return h('section', {
      class: 'panel frame', 'data-key': panel.key,
      style: small ? `flex-basis: ${panel.sensors.length * 176 + 28}px` : null,
    },
      h('header', { class: 'panel-head' },
        h('h2', {}, panel.title),
        h('span', { class: 'tag' }, panel.instance),
        h('span', { class: 'label panel-note' })),
      ...body);
  }));
}

function panelElement(key) {
  return $(`.panel[data-key="${CSS.escape(key)}"]`);
}

function cardElement(root, key) {
  return $(`.card[data-key="${CSS.escape(key)}"]`, root);
}

function updatePanels(panels) {
  for (const panel of panels) {
    const section = panelElement(panel.key);
    section.classList.toggle('stale', panel.stale);
    $('.panel-note', section).textContent = panel.stale && panel.sensors.length
      ? 'Stale — instance unreachable'
      : `${panel.sensors.length} sensor${panel.sensors.length === 1 ? '' : 's'}`;
    if (!panel.sensors.length) {
      $('.placeholder', section).textContent = panel.stale
        ? 'Instance unreachable — see Attention'
        : 'No temperature sensors found on this instance';
      continue;
    }
    for (const sensor of panel.sensors) {
      updateCard(cardElement(section, sensor.key), sensor);
    }
  }
}

function renderHistory() {
  if (!state.dash) return;
  for (const panel of state.dash.panels) {
    const section = panelElement(panel.key);
    if (!section) continue;
    if (state.history) {
      for (const sensor of panel.sensors) {
        renderSpark(cardElement(section, sensor.key), state.history.series[sensor.key] || [], state.history);
      }
    }
    renderChart(panel);
  }
}

// ── Batteries ────────────────────────────────────────────────

function renderBatteries(panels) {
  const signature = JSON.stringify(panels);
  if (signature === state.batteries) return;
  state.batteries = signature;
  const root = $('#batteries');
  root.replaceChildren(...panels.map((panel) => {
    const flagged = panel.items.filter((item) => item.status === 'low' || item.status === 'offline').length;
    return h('section', { class: `panel frame batteries${panel.stale ? ' stale' : ''}` },
      h('header', { class: 'panel-head' },
        h('h2', {}, 'Batteries'),
        h('span', { class: 'tag' }, panel.instance),
        h('span', { class: 'label panel-note' },
          flagged ? `${flagged} of ${panel.items.length} to check` : panel.items.length ? `${panel.items.length} · all good` : '0 sensors')),
      // A house can have the panel before it has the sensors.
      panel.items.length === 0 ? h('p', { class: 'battery-empty' },
        `No battery sensors in ${panel.instance} yet. They will show up here once they are added.`) :
      h('ul', { class: 'battery-grid' }, ...panel.items.map((item) => {
        // Offline and a bare "low" get the icon they have in the attention list
        // rather than a word; the title still says it for a pointer or a screen reader.
        const symbol = (kind, label) => h('span', { class: 'battery-icon', role: 'img', 'aria-label': label, title: label }, icon(kind));
        const value = item.status === 'offline' ? symbol('offline', 'Offline')
          : item.level != null ? `${Math.round(item.level)} %`
          : item.status === 'low' ? symbol('battery', 'Battery low') : item.status === 'ok' ? 'OK' : '—';
        const width = item.status === 'offline' ? 0 : item.level ?? (item.status === 'ok' ? 100 : 0);
        return h('li', { class: 'battery', 'data-status': item.status, title: item.entity },
          h('span', { class: 'battery-name' }, item.name),
          h('span', { class: 'battery-value' }, value),
          h('span', { class: 'battery-meter' }, h('i', { style: `width:${clamp01(width / 100) * 100}%` })));
      })));
  }));
}

// ── History chart ────────────────────────────────────────────

// Line and area paths for a series, lifting the pen over gaps (null values).
function paths(points, x, y, baseline) {
  let line = '';
  let area = '';
  let run = [];
  const flush = () => {
    if (!run.length) return;
    const body = run.map(([px, py]) => `${px.toFixed(1)} ${py.toFixed(1)}`).join('L');
    line += `M${body}`;
    area += `M${run[0][0].toFixed(1)} ${baseline}L${body}L${run.at(-1)[0].toFixed(1)} ${baseline}Z`;
    run = [];
  };
  for (const [t, v] of points) {
    if (v == null) flush();
    else run.push([x(t), y(v)]);
  }
  flush();
  return { line, area };
}

function niceStep(rough) {
  const power = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
}

function timeTicks(start, end, maxTicks) {
  const spanHours = (end - start) / 3600e3;
  const step = [1, 2, 3, 6, 12, 24].find((hours) => spanHours / hours <= maxTicks) || 24;
  const ticks = [];
  const cursor = new Date(start);
  cursor.setMinutes(0, 0, 0);
  for (; cursor.getTime() <= end; cursor.setHours(cursor.getHours() + 1)) {
    if (cursor.getTime() >= start && cursor.getHours() % step === 0) ticks.push(new Date(cursor));
  }
  // At most one label per day beyond that: drop days evenly if still too dense.
  const keepEvery = Math.ceil(ticks.length / maxTicks);
  return ticks.filter((_, index) => (ticks.length - 1 - index) % keepEvery === 0);
}

function nearest(points, t) {
  let best = null;
  for (const point of points) {
    if (point[1] == null) continue;
    if (!best || Math.abs(point[0] - t) < Math.abs(best[0] - t)) best = point;
  }
  return best;
}

// Value of a series at time t, read off the drawn line: interpolated between
// the neighbouring readings, and empty inside a gap.
function valueAt(points, t) {
  let before = null;
  let after = null;
  for (const point of points) {
    if (point[0] <= t) before = point;
    else { after = point; break; }
  }
  if (!before || before[1] == null) return null;
  if (!after || after[1] == null) return before[1];
  return before[1] + ((after[1] - before[1]) * (t - before[0])) / (after[0] - before[0]);
}

function renderChart(panel) {
  const section = panelElement(panel.key);
  const plot = section && $('.chart-plot', section);
  if (!plot || !state.showCharts) return;
  const unit = panel.sensors[0]?.unit;
  $('.legend', section).replaceChildren(
    h('span', {}, h('i', { class: 'swatch' }), `One line per sensor${unit ? ` (${unit})` : ''} — point at the chart to tell them apart`));
  if (state.history) $('.chart', section).classList.remove('loading');
  drawChart(plot, panel.sensors, state.history, { label: panel.title });
}

// Draws the history of one or more sensors into `plot`. A single sensor gets
// a filled line; several get one line each, highlighted by pointing at them.
function drawChart(plot, sensors, history, { label, height = CHART.height, tip = tooltip } = {}) {
  const empty = (message) => plot.replaceChildren(h('p', { class: 'chart-empty' }, message));
  if (!history) return empty('Loading history…');

  const solo = sensors.length === 1;
  const seriesOf = (sensor) => history.series[sensor.key] || [];
  const allPoints = sensors.flatMap(seriesOf).filter((point) => point[1] != null);
  if (!allPoints.length) return empty('No history recorded for this range');

  const width = plot.getBoundingClientRect().width / scale;
  if (!width) return;
  const { left, right, top, bottom } = CHART;
  const innerWidth = width - left - right;
  const baseline = height - bottom;

  let lo = Math.min(...allPoints.map((point) => point[1]));
  let hi = Math.max(...allPoints.map((point) => point[1]));
  if (hi - lo < 1) { lo -= 0.5; hi += 0.5; }
  const step = niceStep((hi - lo) / 4);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;

  const x = (t) => left + ((t - history.start) / (history.end - history.start)) * innerWidth;
  const y = (v) => top + (1 - (v - lo) / (hi - lo)) * (baseline - top);

  const svg = s('svg', {
    viewBox: `0 0 ${width} ${height}`, role: 'img', class: solo ? 'solo' : null, style: `height: ${height}px`,
    'aria-label': `${label}, last ${history.hours} hours`,
  });

  for (let i = 0; i <= Math.round((hi - lo) / step); i++) {
    const value = lo + i * step;
    svg.append(
      s('line', { class: 'grid-line', x1: left, x2: width - right, y1: y(value), y2: y(value) }),
      s('text', { class: 'axis-label', x: left - 8, y: y(value) + 3.5, 'text-anchor': 'end' }, num(value, step < 1 ? 1 : 0)));
  }

  for (const tick of timeTicks(history.start, history.end, Math.max(2, Math.floor(innerWidth / 84)))) {
    const label = tick.getHours() === 0 ? dayFormat.format(tick) : timeFormat.format(tick);
    svg.append(s('text', { class: 'axis-label', x: x(tick.getTime()), y: height - 8, 'text-anchor': 'middle' }, label));
  }

  // A threshold line only makes sense when the whole panel shares it.
  for (const which of ['low', 'critical']) {
    const values = new Set(sensors.map((sensor) => sensor[which]));
    const [value] = values;
    if (values.size !== 1 || value == null || value <= lo || value >= hi) continue;
    svg.append(
      s('line', { class: `threshold ${which}`, x1: left, x2: width - right, y1: y(value), y2: y(value) }),
      s('text', { class: `threshold-label ${which}`, x: left + 6, y: y(value) - 5 }, `${which.toUpperCase()} ${num(value, 0)}`));
  }

  if (solo) {
    svg.append(
      s('defs', {}, s('linearGradient', { id: 'chart-fade', x1: 0, y1: 0, x2: 0, y2: 1 },
        s('stop', { offset: '0%', 'stop-color': 'var(--accent)', 'stop-opacity': 0.24 }),
        s('stop', { offset: '100%', 'stop-color': 'var(--accent)', 'stop-opacity': 0 }))),
      s('path', { d: paths(seriesOf(sensors[0]), x, y, baseline).area, fill: 'url(#chart-fade)' }));
  }
  const lines = new Map(sensors.map((sensor) => [
    sensor.key, s('path', { class: 'line', d: paths(seriesOf(sensor), x, y, baseline).line }),
  ]));
  svg.append(...lines.values());

  const crosshair = s('line', { class: 'crosshair', y1: top, y2: baseline, visibility: 'hidden' });
  const marker = s('circle', { class: 'end-dot', r: 4.5, visibility: 'hidden' });
  const highlight = (key) => {
    svg.classList.toggle('pointing', !solo && key != null);
    for (const [sensorKey, line] of lines) line.classList.toggle('hot', sensorKey === key);
  };
  const hide = () => {
    crosshair.setAttribute('visibility', 'hidden');
    marker.setAttribute('visibility', 'hidden');
    highlight(null);
    tip.hidden = true;
  };
  const hover = (event) => {
    const bounds = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - bounds.left) / bounds.width) * width;
    const pointerY = ((event.clientY - bounds.top) / bounds.height) * height;
    const point = nearest(allPoints, history.start + ((pointerX - left) / innerWidth) * (history.end - history.start));
    if (!point) return hide();

    // The sensor whose line passes closest to the pointer gets the highlight.
    const readings = sensors
      .map((sensor) => ({ sensor, value: valueAt(seriesOf(sensor), point[0]) }))
      .sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity));
    const closest = readings
      .filter((reading) => reading.value != null)
      .reduce((best, reading) => (!best || Math.abs(y(reading.value) - pointerY) < Math.abs(y(best.value) - pointerY) ? reading : best), null);

    setAttrs(crosshair, { x1: x(point[0]), x2: x(point[0]), visibility: 'visible' });
    setAttrs(marker, closest ? { cx: x(point[0]), cy: y(closest.value), visibility: 'visible' } : { visibility: 'hidden' });
    highlight(closest?.sensor.key);

    const when = new Date(point[0]);
    tip.replaceChildren(
      h('div', { class: 'tt-time' }, `${dayFormat.format(when)} · ${timeFormat.format(when)}`),
      ...readings.map(({ sensor, value }) => h('div', { class: `tt-row${sensor === closest?.sensor ? ' hot' : ''}` },
        h('i', { class: 'swatch' }), sensor.name, h('b', {}, withUnit(value, sensor.unit)))));
    tip.hidden = false;
    const box = tip.getBoundingClientRect();
    const tx = event.clientX + 18 + box.width > window.innerWidth ? event.clientX - 18 - box.width : event.clientX + 18;
    const ty = Math.min(window.innerHeight - box.height - 8, Math.max(8, event.clientY - box.height / 2));
    tip.style.left = `${tx / scale}px`;
    tip.style.top = `${ty / scale}px`;
  };

  svg.append(crosshair, marker,
    s('rect', {
      x: left, y: top, width: innerWidth, height: baseline - top, fill: 'transparent',
      onpointermove: hover, onpointerdown: hover, onpointerleave: hide,
    }));
  plot.replaceChildren(svg);
}

// ── Sensor detail overlay ────────────────────────────────────

const findSensor = (key) => state.dash?.panels.flatMap((panel) => panel.sensors.map((sensor) => ({ sensor, panel })))
  .find((entry) => entry.sensor.key === key);

function openDetail(key) {
  const hours = DETAIL_RANGES.some((range) => range.hours === state.hours) ? state.hours : DETAIL_RANGES[0].hours;
  state.detail = { key, hours, history: null };
  $('#detail').showModal();
  renderDetail();
  loadDetail();
}

function closeDetail() {
  $('#detail').close();
}

function setDetailHours(hours) {
  if (!state.detail || state.detail.hours === hours) return;
  state.detail.hours = hours;
  renderDetail();
  loadDetail();
}

function stepDetailRange(delta) {
  const index = DETAIL_RANGES.findIndex((range) => range.hours === state.detail.hours);
  setDetailHours(DETAIL_RANGES[Math.min(DETAIL_RANGES.length - 1, Math.max(0, index + delta))].hours);
}

async function loadDetail() {
  const detail = state.detail;
  const { hours } = detail;
  $('#detail-plot').classList.add('loading');
  try {
    // The page already holds this range when it matches the sparklines.
    let history = state.history?.hours === hours ? state.history : null;
    if (!history) {
      const response = await fetch(`/api/history?hours=${hours}`);
      if (!response.ok) throw new Error(response.statusText);
      history = await response.json();
    }
    if (state.detail !== detail || detail.hours !== hours) return; // closed or switched meanwhile
    detail.history = history;
  } catch (error) {
    console.error('detail history failed', error);
  }
  $('#detail-plot').classList.remove('loading');
  drawDetail();
}

// Header of the overlay; follows the live values while it is open.
function renderDetail() {
  const entry = state.detail && findSensor(state.detail.key);
  if (!entry) return;
  const { sensor, panel } = entry;
  const live = sensor.value != null && sensor.status !== 'offline' && sensor.status !== 'nodata';
  $('#detail-title').textContent = sensor.name;
  $('#detail-instance').textContent = panel.instance;
  const status = $('#detail-status');
  status.textContent = STATUS_LABEL[sensor.status];
  status.dataset.status = sensor.status;
  $('#detail-now').replaceChildren(live ? num(sensor.value) : '—', h('small', {}, sensor.unit));
  $('#detail-range').replaceChildren(...DETAIL_RANGES.map((range) => h('button', {
    type: 'button',
    'aria-pressed': String(range.hours === state.detail.hours),
    onclick: () => setDetailHours(range.hours),
  }, range.label)));
}

function drawDetail() {
  const entry = state.detail && findSensor(state.detail.key);
  if (!entry || !$('#detail').open) return;
  const { sensor } = entry;
  const history = state.detail.history?.hours === state.detail.hours ? state.detail.history : null;
  const values = (history?.series[sensor.key] || []).map((point) => point[1]).filter((value) => value != null);
  const stat = (label, value) => h('span', {}, label, h('b', {}, withUnit(value, sensor.unit)));
  $('#detail-stats').replaceChildren(...(values.length ? [
    stat('MIN', Math.min(...values)),
    stat('AVG', values.reduce((a, b) => a + b, 0) / values.length),
    stat('MAX', Math.max(...values)),
  ] : []));
  drawChart($('#detail-plot'), [sensor], history, { label: sensor.name, height: 460, tip: $('#detail-tooltip') });
}

// ── Doors & motion ───────────────────────────────────────────

const ACTIVITY_LABEL = { door: ['Open', 'Closed'], shade: ['Open', 'Closed'], motion: ['Motion', 'Clear'], other: ['On', 'Off'] };

// How long ago the last change was, as an upper bound that reads at a glance:
// "< 12 minutes", "< 5 hours", and from a day on "< 3 days".
function activityAge(item, now) {
  if (item.since == null) return '';
  const span = Math.max(0, now - item.since);
  const [size, unit] = span < 3600 ? [60, 'minute'] : span < 86400 ? [3600, 'hour'] : [86400, 'day'];
  const count = Math.floor(span / size) + 1;
  return `< ${count} ${unit}${count === 1 ? '' : 's'}`;
}

// How strongly a sensor that has gone quiet still glows: full the moment it
// was last triggered, nothing after a day. The fall is logarithmic, so most
// of it happens in the first hour (about half is left by then) and the rest
// is a long tail: a glance tells "just now" from "this morning".
const GLOW_SPAN = 24 * 3600;
const GLOW_KNEE = 2 * 60;

function activityGlow(item, now) {
  if (item.since == null) return 0;
  const age = Math.max(0, now - item.since);
  if (age >= GLOW_SPAN) return 0;
  return 1 - Math.log1p(age / GLOW_KNEE) / Math.log1p(GLOW_SPAN / GLOW_KNEE);
}

function renderActivity(panels) {
  const now = Date.now() / 1000;
  // The texts are relative times, so they also change when the data doesn't.
  const signature = JSON.stringify(panels) + Math.floor(now / 30);
  if (signature === state.activity) return;
  state.activity = signature;
  $('#activity').replaceChildren(...panels.map((panel) => h('section', { class: `panel frame activity${panel.stale ? ' stale' : ''}` },
    h('header', { class: 'panel-head' },
      h('h2', {}, 'Doors & motion'),
      h('span', { class: 'tag' }, panel.instance),
      h('span', { class: 'label panel-note' }, `${panel.items.length} sensors`)),
    // A house can have the panel before it has the sensors.
    panel.items.length === 0 ? h('p', { class: 'activity-empty' },
      `No door or motion sensors in ${panel.instance} yet. They will show up here once they are added.`) :
    // Most recent change first, so the latest event is always on the left.
    h('ul', { class: 'activity-grid' }, ...[...panel.items].sort((a, b) => (b.since ?? 0) - (a.since ?? 0)).map((item) => {
      const [on, off] = ACTIVITY_LABEL[item.kind] || ACTIVITY_LABEL.other;
      const label = item.status === 'offline' ? 'Offline' : item.active == null ? '—' : item.active ? on : off;
      const changed = item.since ? new Date(item.since * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '';
      // A shade is open for hours on an ordinary day: that is a state, not something to blink about.
      const state = item.status === 'offline' ? 'offline' : item.active && item.kind !== 'shade' ? 'active' : 'idle';
      const glow = state === 'idle' ? activityGlow(item, now) : 0;
      return h('li', {}, h('button', {
        class: 'activity-item', type: 'button', 'data-state': state,
        ...(glow > 0 ? { 'data-recent': '', style: `--glow:${glow.toFixed(3)}` } : {}),
        title: [item.entity, changed && `last change ${changed}`].filter(Boolean).join(' · '),
        onclick: () => openEvents(panel, item, label, state),
      },
        h('span', { class: 'activity-name' }, item.name),
        h('span', { class: 'activity-state' }, label),
        h('span', { class: 'activity-time' }, activityAge(item, now))));
    })))));
  // The panels were just rebuilt, which starts every blink from the top. Put
  // them all on the page's own clock instead, so the beat carries on across
  // rebuilds and all active sensors blink together.
  for (const animation of document.getAnimations()) {
    if (animation.animationName === 'detect') animation.startTime = 0;
  }
}

// ── Lights ───────────────────────────────────────────────────

// "< 12 min", "< 5 h", "< 3 d": how long ago a light was last switched, as an upper bound.
function lightAge(light, now) {
  if (light.since == null) return '';
  const span = Math.max(0, now - light.since);
  const [size, unit] = span < 3600 ? [60, 'min'] : span < 86400 ? [3600, 'h'] : [86400, 'd'];
  return `< ${Math.floor(span / size) + 1} ${unit}`;
}

function renderLights(panels) {
  const now = Date.now() / 1000;
  // The ages are relative, so they change when the data doesn't.
  const signature = JSON.stringify(panels) + Math.floor(now / 30);
  if (signature === state.lights) return;
  state.lights = signature;

  // One box per light: its name, then its room, its state and since when.
  const lightNode = (room) => (light) => {
    const changed = light.since ? new Date(light.since * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '';
    const value = light.status === 'offline' ? 'Offline' : light.status === 'off' ? 'Off'
      : light.brightness != null && light.brightness < 100 ? `${light.brightness} %` : 'On';
    return h('li', {
      class: 'light', 'data-status': light.status,
      // Lit in the colour the light itself reports; the stylesheet has a warm white for the rest.
      style: light.color ? `--lit: rgb(${light.color.join(' ')})` : null,
      title: [light.full_name, light.entity, changed && `last change ${changed}`].filter(Boolean).join(' · '),
    },
      h('span', { class: 'light-name' }, light.name),
      h('span', { class: 'light-room' }, room.name || ''),
      h('span', { class: 'light-state' }, value, h('span', { class: 'light-age' }, lightAge(light, now))));
  };

  const floorNode = (floor) => h('div', { class: 'light-floor' },
    floor.name ? h('h3', { class: 'light-floor-name' }, floor.name) : null,
    h('ul', { class: 'light-grid' }, ...floor.rooms.flatMap((room) => room.lights.map(lightNode(room)))));

  $('#lights').replaceChildren(...panels.map((panel) => h('section', { class: `panel frame lights${panel.stale ? ' stale' : ''}` },
    h('header', { class: 'panel-head' },
      h('h2', {}, 'Lights'),
      h('span', { class: 'tag' }, panel.instance),
      h('span', { class: 'label panel-note' }, panel.total ? `${panel.on} of ${panel.total} on` : 'none found')),
    h('div', { class: 'light-floors' }, ...panel.floors.map(floorNode)))));
}

// What a change to this state is called, per kind of sensor.
const EVENT_LABEL = {
  door: { on: 'Opened', off: 'Closed' },
  shade: { on: 'Opened', off: 'Closed' },
  motion: { on: 'Motion detected', off: 'Motion cleared' },
  other: { on: 'Turned on', off: 'Turned off' },
};

// "45 s" for brief spans, otherwise the usual "3 min" / "2 h 05 min".
const briefly = (seconds) => elapsed(seconds) || `${Math.max(1, Math.round(seconds))} s`;

async function openEvents(panel, item, label, state) {
  const list = $('#events-list');
  $('#events-title').textContent = item.name;
  $('#events-instance').textContent = panel.instance;
  const badge = $('#events-state');
  badge.textContent = label;
  badge.dataset.state = state;
  $('#events-note').textContent = '';
  list.replaceChildren(h('li', { class: 'events-empty' }, 'Loading events…'));
  $('#events').showModal();

  let data;
  try {
    const query = new URLSearchParams({ instance: panel.instance_id, entity: item.entity });
    const response = await fetch(`/api/events?${query}`);
    if (!response.ok) throw new Error(response.statusText);
    data = await response.json();
  } catch (error) {
    console.error('events failed', error);
    list.replaceChildren(h('li', { class: 'events-empty' }, 'Could not load the events'));
    return;
  }
  if ($('#events-title').textContent !== item.name) return; // another sensor was opened meanwhile

  const zone = data.time_zone || undefined;
  const when = new Intl.DateTimeFormat(undefined, {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: zone,
  });
  const names = EVENT_LABEL[data.kind] || EVENT_LABEL.other;
  const now = Date.now() / 1000;
  list.replaceChildren(...(data.events.length ? data.events.map((event) => {
    const offline = event.state === 'unavailable' || event.state === 'unknown';
    const span = event.after == null ? null : `${data.kind === 'door' ? 'open for' : 'lasted'} ${briefly(event.after)}`;
    return h('li', { class: 'event', 'data-state': offline ? 'offline' : event.state === 'on' ? 'active' : 'idle' },
      h('span', { class: 'event-dot' }),
      h('span', { class: 'event-label' }, offline ? 'Went offline' : names[event.state] || event.state, ...(span ? [h('small', {}, span)] : [])),
      h('span', { class: 'event-ago' }, ago(now - event.time)),
      h('span', { class: 'event-when' }, when.format(new Date(event.time * 1000))));
  }) : [h('li', { class: 'events-empty' }, 'No events recorded')]));
  $('#events-note').textContent = [
    data.error && `Home Assistant could not be asked for the history (${data.error}).`,
    `Times are ${data.instance} local time.`,
    'Home Assistant only keeps recent history (10 days by default), so older events are not listed — apart from the most recent change.',
  ].filter(Boolean).join(' ');
}

// ── Attention ────────────────────────────────────────────────

function renderAttention(items) {
  const root = $('#attention');
  const critical = items.filter((item) => item.severity === 'critical').length;
  const warnings = items.length - critical;
  root.dataset.level = critical ? 'critical' : warnings ? 'warning' : 'clear';
  $('#attention-count').textContent = items.length;
  $('#attention-summary').textContent = items.length
    ? [critical && `${critical} critical`, warnings && `${warnings} warning${warnings === 1 ? '' : 's'}`].filter(Boolean).join(' · ')
    : 'Nothing needs you right now';

  const signature = JSON.stringify(items.map((i) => [i.severity, i.kind, i.instance, i.entity, i.title, i.detail, i.key]));
  if (signature !== state.attention) {
    state.attention = signature;
    const list = $('#attention-list');
    if (!items.length) {
      list.replaceChildren(h('li', { class: 'att-clear' }, icon('clear'), h('strong', {}, 'All systems nominal')));
    } else {
      list.replaceChildren(...items.map((item) => {
        const row = h(item.key ? 'button' : 'div', {
          class: 'att-row',
          type: item.key ? 'button' : null,
          onclick: item.key ? () => revealSensor(item.key) : null,
          // The colour says how serious and the icon what kind; spelled out here for a pointer.
          title: `${item.severity === 'critical' ? 'Critical' : 'Warning'} · ${KIND_LABEL[item.kind] || item.kind}`,
        },
          h('span', { class: 'att-icon' }, icon(item.kind)),
          h('span', { class: 'att-text' },
            h('span', { class: 'att-title' }, item.title),
            h('span', { class: 'att-where' }, item.instance),
            h('span', { class: 'att-detail' })));
        return h('li', { class: `att-item ${item.severity}` }, row);
      }));
    }
  }

  // Durations keep counting between rebuilds.
  const details = document.querySelectorAll('#attention-list .att-detail');
  items.forEach((item, index) => {
    const since = item.since ? ` ${duration(Date.now() / 1000 - item.since)}` : '';
    details[index].textContent = `${item.detail || ''}${since}`;
  });
}

function revealSensor(key) {
  const panel = state.dash.panels.find((p) => p.sensors.some((sensor) => sensor.key === key));
  if (!panel) return;
  const card = cardElement(panelElement(panel.key), key);
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  card.classList.remove('flash');
  void card.offsetWidth; // restart the animation
  card.classList.add('flash');
}

// ── Keyboard ─────────────────────────────────────────────────

function stepRange(delta) {
  const index = RANGES.findIndex((range) => range.hours === state.hours);
  const next = RANGES[Math.min(RANGES.length - 1, Math.max(0, index + delta))];
  setHours(next.hours);
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.().catch(() => { /* blocked by the browser */ });
}

function toggleHelp() {
  const help = $('#help');
  if (help.open) help.close();
  else help.showModal();
}

// One table drives both the key handling and the help panel.
const SHORTCUTS = [
  { keys: ['?'], label: 'Show or hide this help', run: toggleHelp },
  { keys: ['F'], label: 'Fullscreen on / off', run: toggleFullscreen },
  { keys: ['H'], label: 'History charts on / off', run: toggleCharts },
  ...RANGES.map((range, index) => ({
    keys: [String(index + 1)],
    label: `History range: ${range.hours < 48 ? `${range.hours} hours` : `${range.hours / 24} days`}`,
    run: () => setHours(range.hours),
  })),
  { keys: ['←'], codes: ['arrowleft'], label: 'Shorter history range', run: () => stepRange(-1) },
  { keys: ['→'], codes: ['arrowright'], label: 'Longer history range', run: () => stepRange(1) },
  { keys: ['R'], label: 'Refresh now', run: () => { refreshDashboard(); refreshHistory(); } },
  { keys: ['Esc'], codes: [], label: 'Close help, history or events / leave fullscreen' },
];

function setupKeyboard() {
  const actions = new Map();
  for (const shortcut of SHORTCUTS) {
    for (const code of shortcut.codes || shortcut.keys.map((key) => key.toLowerCase())) actions.set(code, shortcut.run);
  }
  $('#help-keys').replaceChildren(...SHORTCUTS.flatMap((shortcut) => [
    h('dt', {}, ...shortcut.keys.map((key) => h('kbd', {}, key))),
    h('dd', {}, shortcut.label),
  ]));
  $('#detail-close').addEventListener('click', closeDetail);
  $('#detail').addEventListener('click', (event) => { if (event.target === event.currentTarget) closeDetail(); });
  $('#detail').addEventListener('close', () => { state.detail = null; $('#detail-tooltip').hidden = true; });
  $('#events-close').addEventListener('click', () => $('#events').close());
  $('#events').addEventListener('click', (event) => { if (event.target === event.currentTarget) $('#events').close(); });
  $('#help-open').addEventListener('click', toggleHelp);
  $('#help-close').addEventListener('click', toggleHelp);
  // A click on the dimmed backdrop lands on the dialog element itself.
  $('#help').addEventListener('click', (event) => { if (event.target === event.currentTarget) toggleHelp(); });

  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
    if (event.target.closest?.('input, textarea, select')) return;
    const key = event.key.toLowerCase();
    // While the help is open only "?" acts; Esc is handled by the dialog itself.
    if ($('#help').open && key !== '?') return;
    if ($('#events').open) return;
    // In the sensor overlay the arrows step through its own ranges.
    if ($('#detail').open) {
      if (key === 'arrowleft' || key === 'arrowright') {
        event.preventDefault();
        stepDetailRange(key === 'arrowleft' ? -1 : 1);
      }
      return;
    }
    const action = actions.get(key);
    if (!action) return;
    event.preventDefault();
    action();
  });
}

// ── Data loop ────────────────────────────────────────────────

function render() {
  const dash = state.dash;
  $('#demo-badge').hidden = !dash.demo;
  renderInstances(dash.instances);
  renderWeather(dash.weather || []);
  renderPeople(dash.people || []);

  const structure = JSON.stringify(dash.panels.map((p) => [p.key, p.title, p.instance, p.sensors.map((sensor) => sensor.key)]));
  const rebuilt = structure !== state.structure;
  if (rebuilt) {
    state.structure = structure;
    buildPanels(dash.panels);
  }
  updatePanels(dash.panels);
  if (rebuilt) {
    renderHistory();
    refreshHistory();
  }
  renderActivity(dash.activity || []);
  renderLights(dash.lights || []);
  renderBatteries(dash.batteries || []);
  renderAttention(dash.attention);
  fitSide();
  if ($('#detail').open) renderDetail();
}

async function refreshDashboard() {
  try {
    const response = await fetch('/api/dashboard');
    if (!response.ok) throw new Error(response.statusText);
    state.dash = await response.json();
    state.receivedAt = Date.now();
    state.unreachable = false;
    render();
  } catch (error) {
    console.error('dashboard refresh failed', error);
    state.unreachable = true;
  }
  renderFreshness();
}

async function refreshHistory() {
  const hours = state.hours;
  try {
    const response = await fetch(`/api/history?hours=${hours}`);
    if (!response.ok) throw new Error(response.statusText);
    const history = await response.json();
    if (hours !== state.hours) return; // range changed while loading
    state.history = history;
    renderHistory();
  } catch (error) {
    console.error('history refresh failed', error);
    document.querySelectorAll('.chart.loading').forEach((chart) => chart.classList.remove('loading'));
  }
}

applyScale();
window.addEventListener('resize', applyScale);
document.body.classList.toggle('charts', state.showCharts);
renderRange();
setupKeyboard();
tickClock();
setInterval(tickClock, 1000);
setInterval(renderFreshness, 1000);

await refreshDashboard();
setInterval(refreshDashboard, POLL_MS);
// The server says so the moment a door or motion sensor changes; the poll
// above stays as the fallback. EventSource reconnects on its own.
const stream = new EventSource('/api/stream');
stream.addEventListener('change', refreshDashboard);
// Shown in the top bar, next to the houses' own connections.
const streamIs = (open) => () => { state.stream = open; if (state.dash) renderInstances(state.dash.instances); };
stream.addEventListener('open', streamIs(true));
stream.addEventListener('error', streamIs(false));
setInterval(refreshHistory, HISTORY_REFRESH_MS);

let resizeFrame = 0;
new ResizeObserver(() => {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => {
    state.dash?.panels.forEach(renderChart);
    drawDetail();
  });
}).observe($('#board'));
