"""Guess recto/verso of every scan from the thick outer border of the frame.

The outer border (thick) is at the binding side: right on a recto (a), left on a verso (b).
usage: detect_sides.py FIRST LAST
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

for p in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    a = np.asarray(Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{p:04d}.png').convert('L')) < 128
    band = a[900:2100]
    cols = band.mean(axis=0)
    # thickest dark vertical band (smoothed over 12 px) in the left and right quarters
    k = np.convolve(cols, np.ones(12) / 12, mode='same')
    left, right = k[:500].max(), k[1400:].max()
    side = 'a' if right > left else 'b'
    print(p, side, f'{left:.2f} {right:.2f}')
