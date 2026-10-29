"""Paper textures for the covers: 磁青紙 (indigo) with faint fibres, and the 題簽 slip.

usage: make_cover_bg.py
Writes figures/cover_indigo.jpg (page size at 150 dpi) and figures/slip.jpg.
Generated (seeded) so the covers carry no scanned material.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'figures'
DPI = 150
W, H = round(160.9 / 25.4 * DPI), round(254 / 25.4 * DPI)


def paper(w, h, base, fibre_tone, seed):
    rng = np.random.default_rng(seed)
    a = np.empty((h, w, 3))
    a[:] = base
    # cloudy variation in the pulp
    cloud = Image.fromarray((rng.random((h // 24 + 1, w // 24 + 1)) * 255).astype('uint8'))
    cloud = np.asarray(cloud.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(18)), float) / 255
    a *= (0.94 + 0.10 * cloud)[..., None]
    # short fibres, mostly along the length of the sheet
    fib = Image.new('L', (w, h), 0)
    px = fib.load()
    for _ in range(int(w * h / 900)):
        x, y = rng.integers(0, w), rng.integers(0, h)
        ang = rng.normal(np.pi / 2, 0.5)
        ln = rng.integers(6, 28)
        val = int(rng.integers(40, 120))
        for t in range(ln):
            xx, yy = int(x + t * np.cos(ang)), int(y + t * np.sin(ang))
            if 0 <= xx < w and 0 <= yy < h:
                px[xx, yy] = max(px[xx, yy], val)
    fib = np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), float) / 255
    a = a * (1 - 0.35 * fib[..., None]) + np.array(fibre_tone) * 0.35 * fib[..., None]
    a += rng.normal(0, 2.0, a.shape)          # fine grain
    return Image.fromarray(np.clip(a, 0, 255).astype('uint8'))


OUT.mkdir(exist_ok=True)
paper(W, H, (36, 47, 74), (70, 84, 112), 1).save(OUT / 'cover_indigo.jpg', quality=88)
sw, sh = round(26 / 25.4 * DPI), round(130 / 25.4 * DPI)
paper(sw, sh, (236, 226, 200), (210, 196, 166), 2).save(OUT / 'slip.jpg', quality=90)
print('figures/cover_indigo.jpg', W, H, '; figures/slip.jpg', sw, sh)
