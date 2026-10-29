"""Measure the layout of a half-leaf from the Harvard scan: which cells hold a character.

usage: measure_layout.py SCAN [SCAN ...] [--eval] [--out FILE]

For each PKU scan number (the Harvard half-leaf comes from tools/harvard.py) the frame and
column rules are found as in extract_marks.py; the row phase is set so that cell centres
catch the most ink against the gaps between them. A cell holds a character when the ink
in its centre box exceeds a threshold. Per column: occupied rows -> start, end, count.

--eval compares the occupancy with the proofread transcription (text/v1), cell by cell
and column by column (start row and length), to tune the threshold.
--out writes the skeleton as JSON for tools/flow_text.py.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import extract_marks as em  # noqa: E402
import gen_pages            # noqa: E402
import harvard              # noqa: E402

THRESH = 0.008     # ink fraction of a cell's centre box that counts as a character
                   # (empty cells measure 0.00: show-through is lighter than the ink threshold)


def grid(scan, cfg):
    """(ink mask, top, px, py, xr, ncol, nrow) with columns snapped to the rules."""
    info = cfg['pages'][scan]
    lay = cfg['layouts'][info['layout']]
    a = np.asarray(harvard.half(scan).convert('L'))
    ink = a < em.INK
    ncol, nrow = lay['cols'], lay['rows']
    top, bot, xl, xr = em.find_frame(ink, info['side'], ncol)
    # faint leaves: the ink threshold between this page's paper and its darkest ink
    paper, dark = np.median(a), np.percentile(a, 1)
    ink = a < max(em.INK, paper - 0.40 * (paper - dark))
    # erase the frame's horizontal lines (rows inked across most of the block), so that a
    # grid a little off does not count the top or bottom line as a character
    band = ink[:, int(0.15 * ink.shape[1]): int(0.85 * ink.shape[1])].mean(axis=1)
    lines = np.nonzero(band > 0.35)[0]
    for y in lines:
        ink[max(0, y - 4): y + 5, :] = False
    # snap the columns onto the rules (as in extract_marks.detect)
    prof = ndimage.uniform_filter1d(ink[top + 30: bot - 30].mean(axis=0), 3)
    p0 = (xr - xl) / ncol
    best = (-1, 0.0, p0)
    anchor = xr if info['side'] == 'a' else xl
    for scale in np.linspace(0.985, 1.015, 13):
        p = p0 * scale
        for dx in np.arange(-0.2 * p0, 0.2 * p0 + 1, 2):
            xs = [anchor + dx + (-k if info['side'] == 'a' else k) * p for k in range(1, ncol)]
            sc = sum(prof[int(round(x))] for x in xs if 0 <= x < len(prof))
            if sc > best[0]:
                best = (sc, dx, p)
    _, dx, p = best
    xr = (xr + dx) if info['side'] == 'a' else (xl + dx + ncol * p)
    # rows per column: most leaves have 20 (body 低三格), some (recut?) leaves spread 17
    # characters over the whole column. Take the character pitch from the periodicity of
    # the ink down the column centres.
    centres = [int(xr - (c + 0.5) * p) for c in range(ncol)]
    vprof = sum(ink[top:bot, max(0, x - int(0.2 * p)): x + int(0.2 * p)].mean(axis=1) for x in centres)
    v = vprof - vprof.mean()
    ac = np.correlate(v, v, mode='full')[len(v) - 1:]
    fh = bot - top
    lo_, hi_ = int(fh / 22), int(fh / 15)
    lag = lo_ + int(np.argmax(ac[lo_:hi_]))
    est = fh / lag
    if abs(est - 17) < abs(est - nrow) and abs(est - 17) < 1.2:
        nrow = 17
    py = (bot - top) / nrow
    # row phase: centre boxes against the gaps between them
    ii = np.pad(ink.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def box(x0, y0, x1, y1):
        x0, x1 = max(0, int(x0)), min(ink.shape[1], int(x1))
        y0, y1 = max(0, int(y0)), min(ink.shape[0], int(y1))
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0] if x1 > x0 and y1 > y0 else 0

    bestd = (-1e9, 0)
    for d in range(-int(0.5 * py), int(0.5 * py) + 1, 2):
        s = 0
        for c in range(ncol):
            cx = xr - (c + 0.5) * p
            for r in range(nrow):
                cy = top + (r + 0.5) * py + d
                s += box(cx - 0.25 * p, cy - 0.3 * py, cx + 0.25 * p, cy + 0.3 * py)
                s -= 2 * box(cx - 0.25 * p, cy + 0.42 * py, cx + 0.25 * p, cy + 0.58 * py)
        bestd = max(bestd, (s, d))
    top += bestd[1]
    return ink, box, top, p, py, xr, ncol, nrow


def measure(scan, cfg):
    ink, box, top, px, py, xr, ncol, nrow = grid(scan, cfg)
    measure.rows = nrow
    area = (0.55 * px) * (0.70 * py)
    cols = []
    for c in range(ncol):
        cx = xr - (c + 0.5) * px
        dens = [box(cx - 0.275 * px, top + (r + 0.15) * py, cx + 0.275 * px, top + (r + 0.85) * py) / area
                for r in range(nrow)]
        occ = [d > THRESH for d in dens]
        rows = [r for r, o in enumerate(occ) if o]
        cols.append({'occ': occ, 'dens': [round(d, 3) for d in dens],
                     'start': rows[0] if rows else None, 'end': rows[-1] if rows else None,
                     'count': len(rows)})
    return cols


def truth(scan, cfg):
    """Occupied rows per column from the transcription (main text only)."""
    lay = cfg['layouts'][cfg['pages'][scan]['layout']]
    page = gen_pages.parse_page(gen_pages.text_path(scan, cfg['pages'][scan]))
    out = []
    for start, items in page.columns:
        r = float(lay['indent'] if start is None else start)
        occ = [False] * lay['rows']
        for it in items:
            if it[0] == 'c':
                if 0 <= int(r) < lay['rows']:
                    occ[int(r)] = True
                r += 1
            elif it[0] == 'e':
                r += 1
            else:
                n = max(len(it[1]), len(it[2])) * lay.get('note_pitch', 1.0)
                for k in range(int(round(n))):
                    if 0 <= int(r) + k < lay['rows']:
                        occ[int(r) + k] = True
                r += n
        out.append(occ)
    while len(out) < lay['cols']:
        out.append([False] * lay['rows'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scans', nargs='+', help='page keys or one range like h053L-h077L')
    ap.add_argument('--eval', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
    skel, cells_ok, cells_n, cols_ok, cols_n = {}, 0, 0, 0, 0
    keys = gen_pages.page_range(a.scans[0], cfg) if len(a.scans) == 1 and '-' in a.scans[0][1:] else [gen_pages.page_key(s) for s in a.scans]
    for scan in keys:
        cols = measure(scan, cfg)
        skel[scan] = {'rows': measure.rows, 'cols': [{'start': c['start'], 'end': c['end'], 'count': c['count'], 'occ': [bool(o) for o in c['occ']]} for c in cols]}
        if a.eval:
            t = truth(scan, cfg)
            bad = []
            for c, (col, occ) in enumerate(zip(cols, t)):
                if measure.rows == len(occ):
                    cells_ok += sum(x == y for x, y in zip(col['occ'], occ))
                    cells_n += len(occ)
                rows = [r for r, o in enumerate(occ) if o]
                if measure.rows == 17:   # truth is in the 20-row grid: compare lengths only
                    ok = col['count'] == len(rows)
                else:
                    ok = (col['start'], col['count']) == ((rows[0] if rows else None), len(rows))
                cols_ok += ok
                cols_n += 1
                if not ok:
                    bad.append(f'{c + 1}:{col["start"]}+{col["count"]}≠{rows[0] if rows else None}+{len(rows)}')
            print(scan, f'[{measure.rows} rows]', 'columns off:', ' '.join(bad) if bad else '-')
    if a.eval:
        print(f'cells {cells_ok}/{cells_n} ({cells_ok / cells_n:.1%}), '
              f'columns (start+length) {cols_ok}/{cols_n} ({cols_ok / cols_n:.1%})')
    if a.out:
        Path(a.out).write_text(json.dumps(skel, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
