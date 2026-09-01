// Greyscale -> 1bpp packing in the panel's native bit order:
// MSB is the leftmost pixel, 1 is white, rows are 120 bytes with no padding.
// This is exactly what SSD1677 RAM expects, so the ESP32 streams it through
// without decoding or a second buffer.
import { config } from './config.js';

// Returns the packed frame plus the binarized greyscale it came from, so
// /preview.png can show the real two-tone result rather than the smooth
// screenshot that preceded it.
export function packMono(gray, width, height, options = {}) {
  // Per-call overrides, so a still image can be dithered while the dashboard
  // stays hard-thresholded.
  const threshold = options.threshold ?? config.threshold;
  const dither = options.dither ?? config.dither;

  const rowBytes = width >> 3;
  const frame = Buffer.alloc(rowBytes * height, 0xff);
  const preview = Buffer.alloc(width * height);

  // Copy so the error-diffusion pass does not mutate sharp's buffer, and so
  // accumulated error can exceed 0-255.
  const src = dither ? Int16Array.from(gray) : gray;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      const value = src[i];
      const white = value >= threshold;

      if (!white) {
        // Clear the bit: 0 = black.
        frame[y * rowBytes + (x >> 3)] &= ~(0x80 >> (x & 7));
      }
      preview[i] = white ? 255 : 0;

      if (dither) {
        const err = value - (white ? 255 : 0);
        // Floyd-Steinberg, clipped at the edges.
        if (x + 1 < width) src[i + 1] += (err * 7) / 16;
        if (y + 1 < height) {
          if (x > 0) src[i + width - 1] += (err * 3) / 16;
          src[i + width] += (err * 5) / 16;
          if (x + 1 < width) src[i + width + 1] += (err * 1) / 16;
        }
      }
    }
  }

  return { frame, preview };
}
