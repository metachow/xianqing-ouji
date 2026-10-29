"""Download the base scans: PKU copy of 閒情偶寄 vol. 1 (Internet Archive 02097225.cn).

usage: fetch_pku.py
Writes scans/v1/02097225.cn_NNNN.png (8-bit grey; the originals are 1-bit Group-4 TIFFs
at 300 dpi). Pillow 12 crashes on these TIFFs, so they are decompressed with libtiff's
`tiffcp -c none` first (Anaconda ships it; on Windows it is in Library/bin).
"""
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://archive.org/download/02097225.cn/02097225.cn_tif.zip'
OUT = ROOT / 'scans' / 'v1'

OUT.mkdir(parents=True, exist_ok=True)
tiffcp = shutil.which('tiffcp') or str(Path(shutil.which('python') or 'python').parent / 'Library' / 'bin' / 'tiffcp')
with tempfile.TemporaryDirectory() as tmp:
    z = Path(tmp) / 'tif.zip'
    print('downloading', URL)
    urllib.request.urlretrieve(URL, z)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(tmp)
    for tif in sorted(Path(tmp).rglob('*.tif')):
        png = OUT / (tif.stem + '.png')
        if png.exists():
            continue
        raw = Path(tmp) / 'u.tif'
        subprocess.run([tiffcp, '-c', 'none', str(tif), str(raw)], check=True, capture_output=True)
        Image.open(raw).convert('L').save(png)
        print(png.name)
