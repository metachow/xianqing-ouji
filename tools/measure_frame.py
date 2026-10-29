"""Measure the printed frame (版框) and column rules (界欄) of scan pages.

usage: measure_frame.py PAGE [PAGE ...]
Prints the frame box and the x positions of the vertical rules in pixels and mm
(the scans are 300 dpi), and the mean column pitch.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MM = 25.4 / 300


def runs(mask):
    """Start/end index pairs of consecutive True runs."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


for p in map(int, sys.argv[1:]):
    a = np.asarray(Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{p:04d}.png').convert('L')) < 128
    h, w = a.shape
    # horizontal frame lines: rows with long ink runs
    rows = a.mean(axis=1)
    hr = [r for r in runs(rows > 0.45)]
    top, bot = hr[0][0], hr[-1][1]
    band = a[top + 40:bot - 40]
    cols = band.mean(axis=0)
    vr = [((s + e) / 2, e - s + 1) for s, e in runs(cols > 0.30)]
    xs = [x for x, _ in vr]
    pitch = np.diff(xs)
    print(f'scan {p}: {w}x{h}px  frame rows {hr}')
    print(f'  top {top} ({top*MM:.1f} mm)  bottom {bot} ({bot*MM:.1f} mm)  height {(bot-top)*MM:.1f} mm')
    print('  vertical rules x/width:', [(round(x), wd) for x, wd in vr])
    print('  pitch px:', [round(d) for d in pitch], ' median %.1f px = %.2f mm' % (np.median(pitch), np.median(pitch) * MM))
