// Static images packed for the panel.
//
// Anything dropped into server/images as a PNG becomes available at
// /<name>.bin, ready for the device, and /<name>.png as a preview of what the
// panel will actually show. Meant for experiments — textures, photographs,
// hand-drawn layouts — without disturbing the dashboard pipeline.
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

import { config, frameBytes } from './config.js';
import { packMono } from './pack.js';

const imageDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'images');

// Keyed by name + file mtime + render options, so editing the PNG or changing
// the dithering invalidates automatically.
const cache = new Map();

export function imagePath(name) {
  // Defend the obvious traversal: only bare names, resolved inside imageDir.
  if (!/^[A-Za-z0-9_-]+$/.test(name)) return null;
  return path.join(imageDir, `${name}.png`);
}

export async function packStill(name, options) {
  const file = imagePath(name);
  if (!file) throw Object.assign(new Error('bad image name'), { status: 400 });

  let stat;
  try {
    stat = await fs.stat(file);
  } catch {
    throw Object.assign(new Error(`no image at server/images/${name}.png`), { status: 404 });
  }

  const key = `${name}:${stat.mtimeMs}:${options.threshold}:${options.dither}`;
  const hit = cache.get(key);
  if (hit) return hit;

  const { width, height } = config.panel;
  let image = sharp(file);
  const meta = await image.metadata();

  // The panel always wants native-orientation scanlines. Accept an image in
  // either orientation and rotate a portrait one into place.
  if (meta.width === height && meta.height === width) {
    image = image.rotate(90);
  } else if (meta.width !== width || meta.height !== height) {
    throw Object.assign(
      new Error(`${name}.png is ${meta.width}x${meta.height}, need ${width}x${height} (or ${height}x${width} portrait)`),
      { status: 422 },
    );
  }

  const { data, info } = await image.greyscale().raw().toBuffer({ resolveWithObject: true });
  const { frame, preview } = packMono(data, info.width, info.height, options);
  if (frame.length !== frameBytes) throw new Error(`packed ${frame.length}, expected ${frameBytes}`);

  const png = await sharp(preview, {
    raw: { width: info.width, height: info.height, channels: 1 },
  }).png().toBuffer();

  const result = {
    frame,
    png,
    etag: `"${crypto.createHash('sha1').update(frame).digest('hex')}"`,
  };
  cache.set(key, result);
  return result;
}

// Query overrides, so a texture can be dithered without changing how the
// dashboard renders: /chalk.bin?dither=1&threshold=140
export function renderOptions(query) {
  const threshold = Number(query.threshold);
  return {
    dither: 'dither' in query ? query.dither !== '0' : config.dither,
    threshold: Number.isFinite(threshold) ? threshold : config.threshold,
  };
}

export async function listImages() {
  try {
    return (await fs.readdir(imageDir))
      .filter((f) => f.endsWith('.png'))
      .map((f) => f.replace(/\.png$/, ''));
  } catch {
    return [];
  }
}
