"""Build the PDFs of one volume (冊) or of all.

usage: build.py [--ce N ...] [--only spread|single] [--no-gen]

Regenerates pages (gen_pages.py), the 句讀 layer is left as it is (run wiki_punct.py
after changing text), writes the appendix (gen_appendix.py), then runs XeLaTeX twice
per edition with its own job name and copies the results to
build/xianqing-ouji_ce<N>_<name>_{spread,single}.pdf (name from layout.yaml volumes).
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ce', type=int, nargs='*')
    ap.add_argument('--only', choices=['spread', 'single'])
    ap.add_argument('--no-gen', action='store_true', help='skip gen_pages / gen_appendix')
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
    vols = {v['ce']: v for v in cfg['volumes']}
    if not a.no_gen:
        for tool in ('gen_pages.py', 'gen_appendix.py'):
            r = run([PY, str(ROOT / 'tools' / tool)])
            if r.returncode:
                sys.exit(r.stdout + r.stderr)
    (ROOT / 'build').mkdir(exist_ok=True)
    for ce in a.ce or sorted(vols):
        for kind, main in (('spread', 'main_spread'), ('single', 'main')):
            if a.only and kind != a.only:
                continue
            job = f'ce{ce}_{kind}'
            t0 = time.time()
            for _ in range(2):          # remember picture / links settle on the second run
                r = run(['xelatex', '-interaction=nonstopmode', '-output-directory=build',
                         f'-jobname={job}', f'\\def\\edce{{{ce}}}\\input{{{main}}}'])
            log = (ROOT / 'build' / f'{job}.log').read_text(encoding='utf-8', errors='replace')
            errors = [ln for ln in log.splitlines() if ln.startswith('!')]
            pages = [ln for ln in log.splitlines() if ln.startswith('Output written')]
            out = ROOT / 'build' / f'xianqing-ouji_ce{ce}_{vols[ce]["name"]}_{kind}.pdf'
            if errors or not pages:
                print(f'冊{ce} {kind}: FAILED', *errors[:3], sep='\n  ')
                continue
            shutil.copy(ROOT / 'build' / f'{job}.pdf', out)
            print(f'冊{ce} {kind}: {pages[0].split("(")[1].rstrip(").")} -> {out.name} ({time.time() - t0:.0f} s)')


if __name__ == '__main__':
    main()
