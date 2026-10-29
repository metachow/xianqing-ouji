"""Check transcribed pages: parse, typeset each alone, and put it beside its scan.

usage: check_page.py SCAN [SCAN ...] [--dpi D]

For each scan: generates pages/NNN.tex, compiles it alone in build/check/NNN/
(so several checks can run at the same time), writes work/check/NNN.png
(scan left, edition right, same scale) and prints the rows used by every
column, so that a dropped or doubled character shows as a column of the wrong
length. Exit status 1 if any page failed.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pages  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('scans', nargs='+', type=int)
ap.add_argument('--dpi', type=int, default=100)
a = ap.parse_args()

cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
variants = gen_pages.load_variants()
gen_pages.SHOW_MARKS = cfg.get('show_marks', True)
failed = False
(ROOT / 'work' / 'check').mkdir(parents=True, exist_ok=True)

for s in a.scans:
    scan = f'{s:03d}'
    info = cfg['pages'][scan]
    lay = cfg['layouts'][info['layout']]
    src = ROOT / 'text' / 'v1' / f'{scan}.txt'
    try:
        page = gen_pages.parse_page(src)
        tex = gen_pages.render(scan, info, lay, page, variants, [])
    except (ValueError, FileNotFoundError) as e:
        print(f'{scan}: ERROR {e}')
        failed = True
        continue
    (ROOT / 'pages' / f'{scan}.tex').write_text(tex, encoding='utf-8')

    # column report
    np_ = lay.get('note_pitch', 0.62)
    parts = []
    for c, (start, items) in enumerate(page.columns, 1):
        r0 = lay['indent'] if start is None else start
        used = gen_pages.column_rows(items, np_)
        parts.append(f'{c}:{r0}+{used:g}')
    print(f'{scan} [{info["layout"]} {info["side"]} {info["juan"]}{info["leaf"]}] '
          f'{len(page.columns)}/{lay["cols"]} columns, rows {lay["rows"]}: ' + ' '.join(parts)
          + (f'  眉批 {len(page.notes)}' if page.notes else ''))

    # typeset alone
    d = ROOT / 'build' / 'check' / scan
    d.mkdir(parents=True, exist_ok=True)
    (d / 'page.tex').write_text('\\documentclass{article}\n\\input{preamble}\n\\begin{document}\n'
                                f'\\edpage{{{scan}}}\n\\end{{document}}\n', encoding='utf-8')
    for _ in range(2):      # remember picture: positions settle on the second run
        r = subprocess.run(['xelatex', '-interaction=nonstopmode', '-halt-on-error',
                            f'-output-directory={d}', str(d / 'page.tex')],
                           cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            break
    log = (d / 'page.log').read_text(encoding='utf-8', errors='replace') if (d / 'page.log').exists() else ''
    missing = sorted({line.split('Missing character: There is no ')[1].split(' ')[0]
                      for line in log.splitlines() if 'Missing character' in line})
    if r.returncode or not (d / 'page.pdf').exists():
        print(f'{scan}: ERROR xelatex failed, see {d / "page.log"}')
        failed = True
        continue
    if missing:
        print(f'{scan}: WARNING characters missing in the font: {" ".join(missing)}')

    # side by side
    subprocess.run(['pdftoppm', '-r', str(a.dpi), '-gray', '-png', '-singlefile',
                    str(d / 'page.pdf'), str(d / 'page')], check=True)
    ed = Image.open(d / 'page.png').convert('L')
    sc = Image.open(ROOT / 'scans' / 'v1' / f'02097225.cn_{s:04d}.png').convert('L')
    sc = sc.resize((round(sc.width * a.dpi / 300), round(sc.height * a.dpi / 300)), Image.LANCZOS)
    sheet = Image.new('L', (sc.width + ed.width + 12, max(sc.height, ed.height)), 150)
    sheet.paste(sc, (0, 0))
    sheet.paste(ed, (sc.width + 12, 0))
    out = ROOT / 'work' / 'check' / f'{scan}.png'
    sheet.save(out)
    print(f'{scan}: comparison {out.relative_to(ROOT)}')

sys.exit(1 if failed else 0)
