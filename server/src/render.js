// Headless render of the dashboard page into a packed 1bpp frame.
import crypto from 'node:crypto';
import puppeteer from 'puppeteer';
import sharp from 'sharp';

import { config, frameBytes } from './config.js';
import { packMono } from './pack.js';

const portrait = config.orientation === 'portrait';

// The page is laid out in the mounted orientation, then rotated into the
// panel's native scanline order.
const viewport = portrait
  ? { width: config.panel.height, height: config.panel.width }
  : { width: config.panel.width, height: config.panel.height };

let browser = null;
let inFlight = null;
let cached = null; // { frame, png, etag, renderedAt }

async function getBrowser() {
  if (browser?.connected) return browser;
  browser = await puppeteer.launch({
    headless: true,
    ...(config.chromePath ? { executablePath: config.chromePath } : {}),
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-device-scale-factor=1'],
  });
  return browser;
}

async function screenshot(url) {
  const page = await (await getBrowser()).newPage();
  try {
    await page.setViewport({ ...viewport, deviceScaleFactor: 1 });
    await page.emulateTimezone(config.timeZone);
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30_000 });
    // dashboard.html sets this once it has painted its data.
    await page.waitForFunction('window.__hfReady === true', { timeout: 15_000 });
    return Buffer.from(await page.screenshot({ type: 'png' }));
  } finally {
    await page.close();
  }
}

async function renderOnce(url) {
  const png = await screenshot(url);

  let image = sharp(png);
  if (portrait) image = image.rotate(90);

  const { data, info } = await image
    .greyscale()
    .raw()
    .toBuffer({ resolveWithObject: true });

  if (info.width !== config.panel.width || info.height !== config.panel.height) {
    throw new Error(
      `rendered ${info.width}x${info.height}, panel needs ${config.panel.width}x${config.panel.height}`,
    );
  }

  const { frame, preview } = packMono(data, info.width, info.height);
  if (frame.length !== frameBytes) {
    throw new Error(`packed ${frame.length} bytes, expected ${frameBytes}`);
  }

  const previewPng = await sharp(preview, {
    raw: { width: info.width, height: info.height, channels: 1 },
  }).png().toBuffer();

  return {
    frame,
    png: previewPng,
    // Content-addressed, so an unchanged dashboard costs the device a 304 and
    // the panel stays untouched.
    etag: `"${crypto.createHash('sha1').update(frame).digest('hex')}"`,
    renderedAt: Date.now(),
  };
}

// Serves from cache within the TTL, and collapses concurrent requests onto a
// single browser render.
export async function getFrame(url, { fresh = false } = {}) {
  if (!fresh && cached && Date.now() - cached.renderedAt < config.renderTtlMs) {
    return cached;
  }
  if (inFlight) return inFlight;

  inFlight = renderOnce(url)
    .then((result) => {
      cached = result;
      return result;
    })
    .finally(() => {
      inFlight = null;
    });

  return inFlight;
}

export async function shutdown() {
  if (browser?.connected) await browser.close();
  browser = null;
}
