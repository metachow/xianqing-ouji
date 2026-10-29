"""Write a reading copy of part of a scan page.

usage: crop_view.py PAGE OUT [x0 y0 x1 y1] [--scale S]
PAGE is the scan number (1-based); coordinates are in full-resolution pixels.
"""
import argparse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument('page', type=int)
ap.add_argument('out')
ap.add_argument('box', nargs='*', type=int)
ap.add_argument('--scale', type=float, default=0.5)
a = ap.parse_args()

im = Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{a.page:04d}.png').convert('L')
if a.box:
    im = im.crop(tuple(a.box))
if a.scale != 1:
    im = im.resize((round(im.width * a.scale), round(im.height * a.scale)), Image.LANCZOS)
im.save(a.out)
print(im.size)
