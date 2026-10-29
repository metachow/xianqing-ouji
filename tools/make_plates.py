"""Rebuild all illustration plates (figures/plates/) from the Harvard scans.

usage: make_plates.py
Downloads the illustrated openings if needed (tools/fetch_harvard.py) and runs
tools/clean_plate.py on each half listed below (see figures/README.md for the titles).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATES = ['251R', '252R', '252L', '254R', '254L', '260R', '260L', '261L', '263R', '263L',
          '266R', '266L', '267L', '283L', '284L', '286R', '287R', '288R', '290R', '305R']

for p in PLATES:
    n, side = int(p[:-1]), p[-1]
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'fetch_harvard.py'), str(n), str(n)], check=True)
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'clean_plate.py'), str(n), side, f'h{p}'], check=True)
