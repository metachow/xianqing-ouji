"""Download the Harvard-Yenching copy (HOLLIS 990080074400203941, colour, IIIF).

usage: fetch_harvard.py FIRST LAST        (canvas numbers, 1-based; v.1 = 1-78)

Saves the manifest to scans/harvard/manifest.json and each canvas (one opening =
two half-leaves) at full size as scans/harvard/hNNN.jpg. Skips files already there.
Terms of use: https://nrs.lib.harvard.edu/urn-3:hul.ois:hlviewerterms
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'scans' / 'harvard'
MANIFEST = 'https://mps.lib.harvard.edu/iiif/2/URN-3:FHCL:26853026'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except OSError as e:
            print(f'  retry {attempt + 1}: {e}')
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


OUT.mkdir(parents=True, exist_ok=True)
mpath = OUT / 'manifest.json'
if not mpath.exists():
    mpath.write_bytes(get(MANIFEST))
canvases = json.loads(mpath.read_text(encoding='utf-8'))['sequences'][0]['canvases']
first, last = int(sys.argv[1]), int(sys.argv[2])
for n in range(first, last + 1):
    out = OUT / f'h{n:03d}.jpg'
    if out.exists():
        continue
    svc = canvases[n - 1]['images'][0]['resource']['service']['@id']
    out.write_bytes(get(svc + '/full/full/0/default.jpg'))
    print(n, out.stat().st_size // 1024, 'KB', flush=True)
