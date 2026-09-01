import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { config, frameBytes } from './config.js';
import { collect } from './data.js';
import { recordTelemetry } from './device.js';
import { getFrame, shutdown } from './render.js';
import { listImages, packStill, renderOptions } from './still.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const app = express();

// Shared secret, if configured. The dashboard and preview routes stay open so
// you can iterate on the design in a browser.
app.use('/frame.bin', (req, res, next) => {
  if (!config.token) return next();
  if (req.get('X-Homeframe-Token') === config.token) return next();
  res.status(401).type('text/plain').send('bad or missing X-Homeframe-Token\n');
});

app.use('/static', express.static(path.join(here, '..', 'views')));

app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(here, '..', 'views', 'dashboard.html'));
});

app.get('/api/data', async (req, res) => {
  try {
    res.json(await collect());
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

const dashboardUrl = () => `http://127.0.0.1:${config.port}/dashboard`;

// What the panel fetches: 81600 raw bytes, or 304 when nothing changed.
app.get('/frame.bin', async (req, res) => {
  try {
    // Before rendering, so this frame carries the device's current numbers.
    recordTelemetry(req);

    const { frame, etag } = await getFrame(dashboardUrl(), { fresh: 'fresh' in req.query });

    res.set('ETag', etag);
    res.set('Cache-Control', 'no-cache');
    if (req.get('If-None-Match') === etag) return res.status(304).end();

    res.set('Content-Type', 'application/octet-stream');
    res.set('Content-Length', String(frameBytes));
    res.send(frame);
  } catch (err) {
    console.error('frame render failed:', err);
    res.status(500).type('text/plain').send(`render failed: ${err.message}\n`);
  }
});

// The same render as a PNG — the fast way to iterate on the design without
// touching hardware.
app.get('/preview.png', async (req, res) => {
  try {
    const { png } = await getFrame(dashboardUrl(), { fresh: 'fresh' in req.query });
    res.type('image/png').send(png);
  } catch (err) {
    res.status(500).type('text/plain').send(`render failed: ${err.message}\n`);
  }
});

// --- still images -----------------------------------------------------------
// Registered after /frame.bin and /preview.png so those keep their handlers.
// Any server/images/<name>.png is served packed at /<name>.bin and previewed
// at /<name>.png. Both accept ?dither=1 and ?threshold=N.

app.get('/images', async (req, res) => {
  res.json({ images: await listImages(), dir: 'server/images' });
});

function stillError(res, err) {
  const status = err.status ?? 500;
  if (status === 500) console.error('still render failed:', err);
  res.status(status).type('text/plain').send(`${err.message}\n`);
}

app.get('/:name([A-Za-z0-9_-]+).bin', async (req, res) => {
  try {
    const { frame, etag } = await packStill(req.params.name, renderOptions(req.query));
    res.set('ETag', etag);
    res.set('Cache-Control', 'no-cache');
    if (req.get('If-None-Match') === etag) return res.status(304).end();
    res.set('Content-Type', 'application/octet-stream');
    res.set('Content-Length', String(frameBytes));
    res.send(frame);
  } catch (err) {
    stillError(res, err);
  }
});

app.get('/:name([A-Za-z0-9_-]+).png', async (req, res) => {
  try {
    const { png } = await packStill(req.params.name, renderOptions(req.query));
    res.type('image/png').send(png);
  } catch (err) {
    stillError(res, err);
  }
});

app.get('/healthz', (req, res) => res.json({ ok: true, ...config.panel }));

const server = app.listen(config.port, config.host, () => {
  console.log(`homeframe server on http://localhost:${config.port} (bound ${config.host})`);
  console.log(`  dashboard  /dashboard    (edit views/dashboard.html, reload)`);
  console.log(`  preview    /preview.png  (exactly what the panel will show)`);
  console.log(`  device     /frame.bin    (${frameBytes} bytes, ${config.orientation})`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, async () => {
    await shutdown();
    server.close(() => process.exit(0));
  });
}
