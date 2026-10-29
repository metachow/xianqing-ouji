"""Comparison figures for the README: an opening of the Harvard copy above the same
opening of the re-typeset edition (build/main_spread.pdf).

usage: make_readme_figs.py
Writes docs/compare_<name>.jpg. Build main_spread.pdf first.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import harvard  # noqa: E402

# name: (Harvard opening, a scan on the edition's spread page)
FIGS = {'title': (3, '001c'), 'juanshou': (22, '036'), 'meipi': (26, '044')}
HEIGHT = 900


def spread_page(scan):
    """PDF page number of the opening that holds `scan` in main_spread."""
    page = 0
    for line in (ROOT / 'pages' / 'list_spread.tex').read_text(encoding='utf-8').splitlines():
        if line.startswith('\\edsingle') or line.startswith('\\edspread'):
            page += 1
            if re.search(r'\{' + re.escape(scan) + r'\}', line):
                return page
    raise ValueError(scan)


out = ROOT / 'docs'
out.mkdir(exist_ok=True)
for name, (opening, scan) in FIGS.items():
    orig = Image.open(ROOT / 'scans' / 'harvard' / f'h{opening:03d}.jpg').convert('RGB')
    orig = orig.resize((round(orig.width * HEIGHT / orig.height), HEIGHT), Image.LANCZOS)
    p = spread_page(scan)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['pdftoppm', '-r', '150', '-png', '-singlefile', '-f', str(p), '-l', str(p),
                        str(ROOT / 'build' / 'main_spread.pdf'), str(Path(tmp) / 'p')], check=True)
        ed = Image.open(Path(tmp) / 'p.png').convert('RGB')
    ed = ed.resize((round(ed.width * HEIGHT / ed.height), HEIGHT), Image.LANCZOS)
    w = max(orig.width, ed.width)
    sheet = Image.new('RGB', (w, 2 * HEIGHT + 60), (245, 243, 238))
    d = ImageDraw.Draw(sheet)
    sheet.paste(orig, ((w - orig.width) // 2, 24))
    sheet.paste(ed, ((w - ed.width) // 2, HEIGHT + 54))
    d.text((8, 6), f'Harvard-Yenching copy, opening {opening}', fill=(90, 90, 90))
    d.text((8, HEIGHT + 36), 're-typeset edition', fill=(90, 90, 90))
    f = out / f'compare_{name}.jpg'
    sheet.save(f, quality=82, optimize=True)
    print(f.relative_to(ROOT), sheet.size, f.stat().st_size // 1024, 'KB')
