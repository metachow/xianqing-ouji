"""Scan and edition page side by side at the same scale.

usage: make_comparison.py PDF OUT.png SCAN:PDFPAGE [SCAN:PDFPAGE ...] [--dpi D]
The edition pages have the scans' physical size, so both are shown at D dpi.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument('pdf')
ap.add_argument('out')
ap.add_argument('pairs', nargs='+')
ap.add_argument('--dpi', type=int, default=100)
a = ap.parse_args()

tiles = []
with tempfile.TemporaryDirectory() as tmp:
    for pair in a.pairs:
        scan, page = pair.split(':')
        im = Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{int(scan):04d}.png').convert('L')
        im = im.resize((round(im.width * a.dpi / 300), round(im.height * a.dpi / 300)), Image.LANCZOS)
        base = Path(tmp) / f'p{page}'
        subprocess.run(['pdftoppm', '-r', str(a.dpi), '-gray', '-png', '-f', page, '-l', page,
                        '-singlefile', a.pdf, str(base)], check=True)
        ed = Image.open(str(base) + '.png').convert('L')
        tiles += [im, ed]

gap = 12
w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
h = max(t.height for t in tiles)
sheet = Image.new('L', (w, h), 160)
x = 0
for t in tiles:
    sheet.paste(t, (x, 0))
    x += t.width + gap
sheet.save(a.out)
print(sheet.size)
