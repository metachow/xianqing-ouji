"""Map PKU scans (text/v1/NNN) to half-leaves of the Harvard copy (scans/harvard/hNNN.jpg).

Harvard openings show the b side of one leaf on the right and the a side of the next
leaf on the left. Its binding order differs from the PKU copy (序, 凡例, 總目, 目次,
卷一 against PKU's 序, 總目, 凡例, 目次, 卷一), so the map goes by section and leaf.

usage: harvard.py SCAN OUT.png [x0 y0 x1 y1] [--scale S]
  writes the Harvard half-leaf matching PKU scan SCAN (optionally a crop of it, in
  pixels of the half-leaf image) -- the same interface as crop_view.py.
"""
import argparse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# PKU section: (first PKU scan, Harvard opening whose LEFT half is leaf 1a)
SECTIONS = [(2, 4), (17, 18), (22, 12), (34, 21), (36, 22)]   # 序, 總目, 凡例, 目次, 卷一
ENDS = [16, 21, 33, 35, 94]


def locate(scan):
    """(Harvard opening, 'L' or 'R') for a page key: a PKU vol.-1 scan number (int or '043'),
    or a Harvard half-leaf key 'h053L' (used from 卷二 on, where Harvard is the base)."""
    if isinstance(scan, str) and scan.startswith('h'):
        return int(scan[1:-1]), scan[-1]
    scan = int(scan)
    for (first, open1a), last in zip(SECTIONS, ENDS):
        if first <= scan <= last:
            i = scan - first
            leaf, side = i // 2, 'a' if i % 2 == 0 else 'b'
            return (open1a + leaf, 'L') if side == 'a' else (open1a + leaf + 1, 'R')
    raise ValueError(f'scan {scan} not mapped')


def half(scan, overlap=60):
    """The Harvard half-leaf image for a PKU scan (split at the middle of the opening)."""
    n, lr = locate(scan)
    im = Image.open(ROOT / 'scans' / 'harvard' / f'h{n:03d}.jpg')
    w = im.width // 2
    return im.crop((0, 0, w + overlap, im.height) if lr == 'L' else (w - overlap, 0, im.width, im.height))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('scan')
    ap.add_argument('out')
    ap.add_argument('box', nargs='*', type=int)
    ap.add_argument('--scale', type=float, default=0.5)
    a = ap.parse_args()
    im = half(a.scan).convert('L')
    if a.box:
        im = im.crop(tuple(a.box))
    if a.scale != 1:
        im = im.resize((round(im.width * a.scale), round(im.height * a.scale)), Image.LANCZOS)
    im.save(a.out)
    n, lr = locate(a.scan)
    print(f'Harvard opening {n} {"left" if lr == "L" else "right"} half; saved {im.size}')
