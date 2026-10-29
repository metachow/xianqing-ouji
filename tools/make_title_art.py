"""Cut the 隸書 title of the 扉葉 from the Harvard scan as an ink layer.

usage: make_title_art.py
Reads scans/harvard/h003.jpg (opening 3, right half = the 扉葉), crops the middle
column, divides out the paper (grey closing estimates the background, so stains and
uneven paper go), turns ink density into alpha, keeps only the four large characters
(drops the column rules and the small marks), and writes figures/title_lishu.png
(warm black on transparent). Harvard Library asserts no copyright in reproductions of
public-domain works (library.harvard.edu/policy-access-digital-reproductions-works-public-domain).
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
BOX = (2330, 520, 3080, 2600)          # middle column of the 扉葉 in h003.jpg
INK = (34, 28, 22)

im = Image.open(ROOT / 'scans' / 'harvard' / 'h003.jpg').crop(BOX).convert('L')
g = np.asarray(im, float)

# paper background: grey closing (removes dark strokes) on a reduced copy, smoothed
small = g[::4, ::4]
bg = ndimage.grey_closing(small, size=(41, 41))
bg = ndimage.uniform_filter(bg, 15)
bg = np.asarray(Image.fromarray(bg.astype('float32')).resize(im.size, Image.BILINEAR))
norm = g / np.maximum(bg, 1)

alpha = np.clip((0.82 - norm) / (0.82 - 0.40), 0, 1)

# keep the big characters only
mask = alpha > 0.35
lab, n = ndimage.label(mask)
keep = np.zeros(n + 1, bool)
W = g.shape[1]
for k, sl in enumerate(ndimage.find_objects(lab), 1):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    area = (lab[sl] == k).sum()
    cx = (sl[1].start + sl[1].stop) / 2
    rule = (w < 30 and h > 3 * w) or (w > 0.5 * W and h < 40)   # column rules, frame line
    central = 0.12 * W < cx < 0.88 * W                           # rules and marks lie at the edges
    thin = (min(h, w) < 25 or area < 0.2 * h * w) and area < 3000  # bits of the frame line (also L-shaped corners)
    keep[k] = area > 400 and central and not rule and not thin
grow = ndimage.binary_dilation(keep[lab], iterations=3)   # keep the soft edges too
alpha = alpha * grow

out = np.zeros(g.shape + (4,), 'uint8')
out[..., :3] = INK
out[..., 3] = (alpha * 255).astype('uint8')
ys, xs = np.nonzero(alpha > 0.05)
out = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
(ROOT / 'figures').mkdir(exist_ok=True)
Image.fromarray(out, 'RGBA').save(ROOT / 'figures' / 'title_lishu.png')
print('figures/title_lishu.png', out.shape[1], 'x', out.shape[0])
