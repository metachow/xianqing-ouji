"""Contact sheets of the Harvard copy, to find pages (e.g. illustrations) quickly.

usage: harvard_thumbs.py FIRST LAST [--width W]
Downloads small IIIF renderings of canvases FIRST..LAST into work/hv_thumbs/ and writes
work/hv_sheet_FIRST-LAST.png (openings right to left, numbered, 8 per row).
"""
import argparse
import json
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}

ap = argparse.ArgumentParser()
ap.add_argument('first', type=int)
ap.add_argument('last', type=int)
ap.add_argument('--width', type=int, default=220)
a = ap.parse_args()

canvases = json.loads((ROOT / 'scans' / 'harvard' / 'manifest.json').read_text(encoding='utf-8'))
canvases = canvases['sequences'][0]['canvases']
d = ROOT / 'work' / 'hv_thumbs'
d.mkdir(parents=True, exist_ok=True)
tiles = []
for n in range(a.first, a.last + 1):
    f = d / f't{n:03d}.jpg'
    if not f.exists():
        svc = canvases[n - 1]['images'][0]['resource']['service']['@id']
        req = urllib.request.Request(f'{svc}/full/{a.width},/0/default.jpg', headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            f.write_bytes(r.read())
    im = Image.open(f).convert('L')
    ImageDraw.Draw(im).text((4, 4), str(n), fill=0)
    tiles.append(im)
per = 8
w = max(t.width for t in tiles) + 6
h = max(t.height for t in tiles) + 6
rows = (len(tiles) + per - 1) // per
sheet = Image.new('L', (per * w, rows * h), 128)
for k, t in enumerate(tiles):
    r, c = divmod(k, per)
    sheet.paste(t, ((per - 1 - c) * w, r * h))
out = ROOT / 'work' / f'hv_sheet_{a.first}-{a.last}.png'
sheet.save(out)
print(out, sheet.size)
