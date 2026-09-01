"""Small numpy/OpenCV noise helpers shared by the handwriting and chalk models."""
import cv2
import numpy as np


def value_noise(shape, scale, rng):
    """Smooth value noise in [0, 1].

    `scale` is the feature size in samples, either a scalar or (scale_y, scale_x)
    for anisotropic noise (used for chalk striations: long along the stroke,
    narrow across it).
    """
    h, w = shape
    sy, sx = (scale, scale) if np.isscalar(scale) else scale
    gh = int(np.ceil(h / sy)) + 3
    gw = int(np.ceil(w / sx)) + 3
    grid = rng.random((gh, gw), dtype=np.float32)
    big = cv2.resize(grid, (int(np.ceil(gw * sx)), int(np.ceil(gh * sy))),
                     interpolation=cv2.INTER_CUBIC)
    return np.clip(big[:h, :w], 0.0, 1.0)


def fbm(shape, scale, rng, octaves=3, gain=0.5):
    """Fractal sum of value_noise octaves, normalised to [0, 1]."""
    out = np.zeros(shape, np.float32)
    amp, total = 1.0, 0.0
    for i in range(octaves):
        out += amp * value_noise(shape, scale / (2 ** i), rng)
        total += amp
        amp *= gain
    return out / total


def noise1d(n, scale, rng):
    """Smooth noise in [-1, 1] over n samples with features ~`scale` samples wide."""
    if n <= 0:
        return np.zeros(0, np.float32)
    k = int(np.ceil(n / scale)) + 3
    knots = rng.uniform(-1.0, 1.0, (1, k)).astype(np.float32)
    big = cv2.resize(knots, (int(np.ceil(k * scale)), 1), interpolation=cv2.INTER_CUBIC)
    return np.clip(big[0, :n], -1.0, 1.0)


def smooth1d(a, sigma):
    """Gaussian smoothing of a 1-D signal with edge replication (no shrink at the ends)."""
    if sigma <= 0.3 or len(a) < 3:
        return a
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(a, r, mode='edge'), k, mode='valid')


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)
