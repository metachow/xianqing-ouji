"""Several scans side by side (right to left, in reading order) at a reduced scale.

usage: montage.py OUT.png SCAN [SCAN ...] [--scale S]
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('scans', nargs='+', type=int)
ap.add_argument('--scale', type=float, default=0.25)
a = ap.parse_args()

tiles = []
for s in a.scans:
    im = Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{s:04d}.png').convert('L')
    im = im.resize((round(im.width * a.scale), round(im.height * a.scale)), Image.LANCZOS)
    ImageDraw.Draw(im).text((8, 8), str(s), fill=0)
    tiles.append(im)
gap = 8
w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
sheet = Image.new('L', (w, max(t.height for t in tiles)), 128)
x = w
for t in tiles:          # first scan at the right
    x -= t.width
    sheet.paste(t, (x, 0))
    x -= gap
sheet.save(a.out)
print(sheet.size)
