"""Clean an illustrated half-leaf of the Harvard copy into an ink layer.

usage: clean_plate.py OPENING SIDE NAME [--lo L] [--hi H]
  OPENING  Harvard canvas number (scans/harvard/hNNN.jpg), SIDE  R or L half
Writes figures/plates/NAME.png (warm black ink on transparent, full resolution) and
work/plates/NAME_preview.png (on white, half size).

The paper is thin and the text on the back shows through as grey. In the blue
channel the yellow paper is dark and the grey show-through is close to it, while the
ink is dark in every channel; so: blue channel, divided by the paper background
(grey closing), ink alpha = (hi - x) / (hi - lo) clipped -- hi set below the
show-through level -- and specks removed. Harvard Library asserts no copyright in
reproductions of public-domain works.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
INK = (30, 25, 20)

ap = argparse.ArgumentParser()
ap.add_argument('opening', type=int)
ap.add_argument('side', choices=['R', 'L'])
ap.add_argument('name')
ap.add_argument('--lo', type=float, default=0.45)
ap.add_argument('--hi', type=float, default=0.80)
a = ap.parse_args()

im = Image.open(ROOT / 'scans' / 'harvard' / f'h{a.opening:03d}.jpg')
w = im.width // 2
im = im.crop((0, 0, w + 40, im.height) if a.side == 'L' else (w - 40, 0, im.width, im.height))
b = np.asarray(im, float)[..., 2]

# paper background: grey closing removes the (thin) lines; smooth and scale back up
small = b[::4, ::4]
bg = ndimage.uniform_filter(ndimage.grey_closing(small, size=(31, 31)), 21)
bg = np.asarray(Image.fromarray(bg.astype('float32')).resize(im.size, Image.BILINEAR))
norm = b / np.maximum(bg, 1)

alpha = np.clip((a.hi - norm) / (a.hi - a.lo), 0, 1)
# drop specks: components (at alpha > 0.3) smaller than ~0.3 mm square
lab, n = ndimage.label(alpha > 0.3)
sizes = ndimage.sum(np.ones_like(alpha), lab, range(1, n + 1))
keep = np.concatenate([[False], sizes >= 12])
# the page edges and the shadow of the fold are no ink: drop what touches the image border
for edge in (lab[0], lab[-1], lab[:, 0], lab[:, -1]):
    keep[np.unique(edge)] = False
alpha = alpha * ndimage.binary_dilation(keep[lab], iterations=2)

# the frame (版框), found by projection (its lines are broken, so not one component):
# top and bottom = the outermost long dark rows in the upper / lower part, sides = the
# outermost dark columns between them; keep only what lies inside, and crop to it
ink = alpha > 0.5
H, W = ink.shape
rows = ink[:, W // 5: 4 * W // 5].mean(axis=1)
tops = [y for y in range(int(0.08 * H), int(0.35 * H)) if rows[y] > 0.35]
bots = [y for y in range(int(0.70 * H), int(0.97 * H)) if rows[y] > 0.35]
fy0 = tops[0] if tops else 0
fy1 = bots[-1] + 1 if bots else H
cols = ink[fy0 + 40: fy1 - 40].mean(axis=0)
# candidate vertical lines (the 版心-side rule is thin and broken, so a low threshold);
# the sides are the strongest pair whose spacing fits the block (frame, with or without
# the 版心 strip: 0.64-0.85 of the frame height); none -> keep the full width
lines = []
x = 40
while x < W - 40:
    if cols[x] > 0.2:
        x1_ = x
        while x1_ < W - 40 and cols[x1_] > 0.2:
            x1_ += 1
        seg = cols[x:x1_]
        lines.append((x + int(np.argmax(seg)), float(seg.max())))
        x = x1_
    x += 1
hgt = max(1, fy1 - fy0)
pairs = [(sa + sb, a_, b_) for i, (a_, sa) in enumerate(lines) for b_, sb in lines[i + 1:]
         if 0.64 <= (b_ - a_) / hgt <= 0.85]
if pairs:
    _, fx0, fx1 = max(pairs)
    fx1 += 1
else:
    fx0, fx1 = 40, W - 40
m = 12
y0, y1 = max(0, fy0 - m), min(H, fy1 + m)
x0, x1 = max(0, fx0 - m), min(W, fx1 + m)
alpha = alpha[y0:y1, x0:x1]

out = np.zeros(alpha.shape + (4,), 'uint8')
out[..., :3] = INK
out[..., 3] = (alpha * 255).astype('uint8')
(ROOT / 'figures' / 'plates').mkdir(parents=True, exist_ok=True)
Image.fromarray(out, 'RGBA').save(ROOT / 'figures' / 'plates' / f'{a.name}.png')

prev = Image.new('RGBA', (out.shape[1], out.shape[0]), (255, 255, 255, 255))
prev.alpha_composite(Image.fromarray(out, 'RGBA'))
(ROOT / 'work' / 'plates').mkdir(parents=True, exist_ok=True)
prev = prev.convert('L')
prev.resize((prev.width // 2, prev.height // 2), Image.LANCZOS).save(ROOT / 'work' / 'plates' / f'{a.name}_preview.png')
print(f'figures/plates/{a.name}.png', out.shape[1], 'x', out.shape[0])
