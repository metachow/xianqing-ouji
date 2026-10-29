"""Detect 圈點 beside each character in the Harvard copy.

usage: extract_marks.py SCAN [SCAN ...] [--debug]

For each PKU scan number: takes the matching Harvard half-leaf (tools/harvard.py),
finds the frame and column rules, lays the layout grid over it, and looks for an
ink blob in the gutter at the lower right of every character the transcription
has (text/v1/NNN.txt). Each blob is classified as circle (has a hole), dot
(solid, round) or tick (solid, elongated). Prints, per page, the agreement with
the marks in the transcription and the cells where they differ; --debug writes
work/marks/NNN.png with the grid and the detections drawn on the scan.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pages   # noqa: E402
import harvard     # noqa: E402

INK = 115           # grey level below which a pixel is ink (paper ~180, ink ~60, show-through ~140)
MARK_INK = 135      # looser, for the faint rings of the marks (gutters have little show-through)


def runs(mask):
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


def find_frame(ink, side, ncol):
    """(top, bottom, x_left, x_right) of the text area in pixels."""
    h, w = ink.shape
    rows = ink[:, w // 5: 4 * w // 5].mean(axis=1)
    # frame lines: long dark rows, thin; the top one in the upper third, the bottom one in
    # the lower fifth but clear of the page edge (frame height is ~0.72 of the half-leaf)
    hl = [r for r in runs(rows > 0.40) if r[1] - r[0] < 40]
    tops = [r for r in hl if 0.08 * h < r[0] < 0.33 * h]
    bots = [r for r in hl if 0.75 * h < r[1] < 0.96 * h]
    # several long dark rows can qualify (a stroke inside the frame, the page edge): take the
    # one nearest where the frame lines sit on these leaves (0.19 and 0.91 of the height)
    top = min(tops, key=lambda r: abs(r[1] - 0.19 * h))[1] if tops else int(0.19 * h)
    bot = min(bots, key=lambda r: abs(r[0] - 0.91 * h))[0] if bots else int(0.91 * h)
    # the outer border (thick) is on the binding side: left on a verso, right on a recto;
    # the text area has the block's fixed proportions, so the other edge follows from it
    band = ink[top + 30: bot - 30]
    cols = ndimage.uniform_filter1d(band.mean(axis=0), 9)
    # the width/height ratio varies between copies with paper shrinkage (PKU 0.65,
    # Harvard 0.69): take the strongest rule within that range of the outer border
    lo, hi = int(0.60 * (bot - top)), int(0.74 * (bot - top))
    # outer border: the outermost line that is nearly as strong as the strongest one
    # (heavy vertical strokes of the large 序 characters can beat it otherwise);
    # skip the overlap/gutter shadow at the edge of the half-leaf
    if side == 'b':
        zone = cols[80: int(w * 0.35)]
        outer = 80 + int(np.nonzero(zone > 0.7 * zone.max())[0][0])
        outer += int(np.argmax(cols[outer: outer + 12]))
        seg = cols[outer: min(w, outer + hi)]
    else:
        z0 = int(w * 0.65)
        zone = cols[z0: w - 80]
        outer = z0 + int(np.nonzero(zone > 0.7 * zone.max())[0][-1])
        outer = outer - 11 + int(np.argmax(cols[outer - 11: outer + 1]))
        seg = cols[max(0, outer - hi): outer][::-1]
    # column pitch from the periodic column rules (autocorrelation of the profile)
    s = seg - seg.mean()
    ac = np.correlate(s, s, mode='full')[len(s) - 1:]
    l0, l1 = int(lo / ncol), int(hi / ncol) + 1
    pitch = l0 + int(np.argmax(ac[l0:l1]))
    width = pitch * ncol
    return (top, bot, outer, outer + width) if side == 'b' else (top, bot, outer - width, outer)


def classify(comp):
    hh, ww = comp.shape
    area = comp.sum()
    # close small gaps so that a ring printed as a C still encloses a hole
    closed = ndimage.binary_closing(np.pad(comp, 4), iterations=3)[4:-4, 4:-4] | comp
    filled = ndimage.binary_fill_holes(closed)
    area = closed.sum()
    hole = filled.sum() - area
    elong = max(hh, ww) / max(1, min(hh, ww))
    if elong > 1.6:
        return 'tick'
    # ring or dot: a ring (closed, or printed as a C) has paper in its middle
    cy0, cy1 = int(hh * 0.3), max(int(hh * 0.3) + 1, int(hh * 0.7))
    cx0, cx1 = int(ww * 0.3), max(int(ww * 0.3) + 1, int(ww * 0.7))
    centre = comp[cy0:cy1, cx0:cx1].mean()
    if centre < 0.45 or hole > 0.12 * filled.sum():
        return 'circle'
    return 'dot'


def detect(scan, cfg):
    info = cfg['pages'][scan]
    lay = cfg['layouts'][info['layout']]
    page = gen_pages.parse_page(ROOT / 'text' / 'v1' / f'{scan}.txt')
    im = harvard.half(int(scan)).convert('L')
    a = np.asarray(im)
    ink = a < INK
    # marks are faint on greyer leaves: put the mark threshold between this page's
    # paper (median) and ink (darkest percent) levels
    paper_lv, ink_lv = np.median(a), np.percentile(a, 1)
    mark_ink = paper_lv - 0.30 * (paper_lv - ink_lv)
    ncol, nrow = lay['cols'], lay['rows']
    top, bot, xl, xr = find_frame(ink, info['side'], ncol)
    # snap the column grid onto the rules: small shift and pitch change that put the
    # most rule ink under the grid lines
    prof = ndimage.uniform_filter1d(ink[top + 30: bot - 30].mean(axis=0), 3)
    p0 = (xr - xl) / ncol
    best = (-1, 0.0, p0)
    for scale in np.linspace(0.985, 1.015, 13):
        p = p0 * scale
        for dx in np.arange(-0.2 * p0, 0.2 * p0 + 1, 2):
            anchor = xr if info['side'] == 'a' else xl        # the outer border stays put
            xs = [anchor + dx + (-k if info['side'] == 'a' else k) * p for k in range(1, ncol)]
            sc = sum(prof[int(round(x))] for x in xs if 0 <= x < len(prof))
            if sc > best[0]:
                best = (sc, dx, p)
    _, dx, p = best
    if info['side'] == 'a':
        xr = xr + dx
        xl = xr - ncol * p
    else:
        xl = xl + dx
        xr = xl + ncol * p
    px, py = (xr - xl) / ncol, (bot - top) / nrow
    mm = (bot - top) / gen_pages.FRAME_H          # pixels per mm
    rmin, rmax = 0.7 * mm, 3.2 * mm                # plausible mark size
    found, expected, cells = {}, {}, []
    np_ = lay.get('note_pitch', 0.62)
    for c, (start, items) in enumerate(page.columns):
        r = float(lay['indent'] if start is None else start)
        for it in items:
            if it[0] == 'c':
                cells.append((c, r, it[1], it[2]))
                r += 1
            elif it[0] == 'e':
                r += 1
            else:
                r += max(len(it[1]), len(it[2])) * np_
    # the frame line can be found a little off; align the rows on the glyphs themselves:
    # shift the grid vertically so that the cells holding characters catch the most ink
    ii = np.pad(ink.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def box_sum(x0, y0, x1, y1):
        x0, x1 = max(0, int(x0)), min(ink.shape[1], int(x1))
        y0, y1 = max(0, int(y0)), min(ink.shape[0], int(y1))
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0] if x1 > x0 and y1 > y0 else 0

    best = (-1, 0)
    for d in range(-int(0.5 * py), int(0.5 * py) + 1, 2):
        score = sum(box_sum(xr - (c + 0.5) * px - 0.25 * px, top + (r + 0.5) * py + d - 0.3 * py,
                            xr - (c + 0.5) * px + 0.25 * px, top + (r + 0.5) * py + d + 0.3 * py)
                    for c, r, _, _ in cells)
        best = max(best, (score, d))
    top += best[1]

    for c, r, ch, mk in cells:
        cx = xr - (c + 0.5) * px
        cy = top + (r + 0.5) * py
        # the gutter between the glyph's right edge and the column rule; in the 序 the
        # (large) marks sit on the rule itself (layout key mark_on_rule)
        on_rule = lay.get('mark_on_rule', False)
        if on_rule:     # beside or on the rule: from the glyph's edge to just past the rule
            x0, x1 = int(cx + 0.27 * px), int(cx + 0.5 * px + 2.2 * mm)
        else:
            x0, x1 = int(cx + 0.29 * px), int(cx + 0.5 * px + 0.3 * mm)
        y0, y1 = int(cy - 0.42 * py), int(cy + 0.50 * py)   # marks sit beside the glyph, a little low
        win = (a[y0:y1, x0:x1] < mark_ink).copy()
        rule_x = cx + 0.5 * px - x0                     # the column rule, in window coordinates
        if win.size == 0:
            found[(c, round(r, 2))] = (None, ch, None)
            expected[(c, round(r, 2))] = mk
            continue
        # erase the column rule (pixel columns inked over most of a taller band) so
        # that circles touching it come apart from it
        if not on_rule:     # a ring crossed by the rule still has holes: keep the rule then
            band = ink[int(cy - 1.5 * py):int(cy + 1.5 * py), x0:x1]
            win[:, band.mean(axis=0) > 0.45] = False
        lab, n = ndimage.label(win)
        pieces = []
        for k, sl in enumerate(ndimage.find_objects(lab), 1):
            comp = lab[sl] == k
            hh, ww = comp.shape
            if comp.sum() < 0.08 * rmin * rmin or max(hh, ww) > rmax:
                continue
            if hh > 2.5 * ww and hh > rmin:    # a piece of the column rule
                continue
            if hh > 1.6 * ww and sl[1].start > win.shape[1] - 0.6 * mm:   # rule fragment at the edge
                continue
            xc = (sl[1].start + sl[1].stop) / 2
            if not on_rule and abs(xc - rule_x) < 0.06 * px and hh >= ww:  # dash of a dotted rule
                continue
            if on_rule and hh > 2.2 * ww:                  # the rule itself
                continue
            pieces.append((comp.sum(), sl))
        box = None
        if pieces:
            # a ring often prints as two arcs: merge the pieces near the largest one
            pieces.sort(key=lambda p: -p[0])
            sl0 = pieces[0][1]
            yc, xc = (sl0[0].start + sl0[0].stop) / 2, (sl0[1].start + sl0[1].stop) / 2
            ys0, ys1, xs0, xs1 = sl0[0].start, sl0[0].stop, sl0[1].start, sl0[1].stop
            for _, sl in pieces[1:]:
                if abs((sl[0].start + sl[0].stop) / 2 - yc) < 0.9 * rmax / 2 and \
                   abs((sl[1].start + sl[1].stop) / 2 - xc) < 0.9 * rmax / 2:
                    ys0, ys1 = min(ys0, sl[0].start), max(ys1, sl[0].stop)
                    xs0, xs1 = min(xs0, sl[1].start), max(xs1, sl[1].stop)
            if max(ys1 - ys0, xs1 - xs0) >= rmin and win[ys0:ys1, xs0:xs1].sum() >= 0.3 * rmin * rmin:
                box = (ys0, ys1, xs0, xs1)
        kind = classify(win[box[0]:box[1], box[2]:box[3]]) if box else None
        found[(c, round(r, 2))] = (kind, ch, box and (x0 + box[2], y0 + box[0], x0 + box[3], y0 + box[1]))
        expected[(c, round(r, 2))] = mk
    smooth(found)
    return im, (top, bot, xl, xr, px, py), found, expected


def smooth(found):
    """Context rules over the page in reading order (columns right to left, top down):
    dense circles (密圈) run without gaps, so
    - a single cell with no mark or a 'tick' (usually a broken ring) between two
      circles/dots becomes a circle;
    - a gap of two such cells is filled too when it sits inside a run, i.e. at least
      two marked cells on each side (plain text has single clause marks, never runs)."""
    keys = sorted(found, key=lambda k: (k[0], k[1]))
    kinds = [found[k][0] for k in keys]
    ring = {'circle', 'dot'}
    n = len(keys)

    def fill(i):
        kind, ch, box = found[keys[i]]
        found[keys[i]] = ('circle', ch, box)
        kinds[i] = 'circle'

    for i in range(1, n - 1):
        if kinds[i - 1] in ring and kinds[i + 1] in ring and kinds[i] in (None, 'tick'):
            fill(i)
    for i in range(2, n - 3):
        gap = kinds[i] in (None, 'tick') and kinds[i + 1] in (None, 'tick')
        if gap and all(kinds[j] in ring for j in (i - 2, i - 1, i + 2, i + 3)):
            fill(i)
            fill(i + 1)


SYMBOL = {'circle': '。', 'dot': '•', 'tick': '、', None: ''}


def rewrite(scan, found):
    """Write the detected marks into text/v1/NNN.txt: main-text characters get the
    detected mark (and lose { } and old marks); notes, 眉批 and placed text keep theirs."""
    path = ROOT / 'text' / 'v1' / f'{scan}.txt'
    cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
    lay = cfg['layouts'][cfg['pages'][scan]['layout']]
    np_ = lay.get('note_pitch', 0.62)
    out, col = [], 0

    def cells(cs):
        return ''.join(('　' if c[0] == 'e' else c[1] + SYMBOL[c[2]]) for c in cs)

    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.rstrip()
        if line.startswith('#') or line.startswith('@'):
            out.append(line)
            continue
        prefix = ''
        body = line
        if line.startswith('^'):
            m = 1
            while m < len(line) and (line[m].isdigit() or (m == 1 and line[m] == '-')):
                m += 1
            prefix, body = line[:m] + ' ', line[m:].lstrip(' ')
        items, _ = gen_pages.parse_items(body, False)
        start = lay['indent'] if not prefix else int(prefix[1:])
        r, parts = float(start), []
        for it in items:
            if it[0] == 'c':
                kind = found.get((col, round(r, 2)), (None,))[0]
                parts.append(it[1] + SYMBOL[kind])
                r += 1
            elif it[0] == 'e':
                parts.append('　')
                r += 1
            else:
                parts.append('〔' + cells(it[1]) + ('|' + cells(it[2]) if it[2] else '') + '〕')
                r += max(len(it[1]), len(it[2])) * np_
        out.append(prefix + ''.join(parts))
        col += 1
    path.write_text('\n'.join(out) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scans', nargs='+', type=int)
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--write', action='store_true', help='write the detected marks into text/v1')
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
    total = agree = 0
    for s in a.scans:
        scan = f'{s:03d}'
        im, (top, bot, xl, xr, px, py), found, expected = detect(scan, cfg)
        if a.write:
            if cfg['layouts'][cfg['pages'][scan]['layout']].get('marks') != 'script':
                print(f'{scan}: layout does not say `marks: script`; text/v1 left as it is')
            else:
                rewrite(scan, found)
        diffs = []
        for key, (kind, ch, box) in found.items():
            total += 1
            if kind == expected[key]:
                agree += 1
            else:
                diffs.append(f'{key[0]+1}/{int(key[1])+1}{ch}:{expected[key] or "-"}→{kind or "-"}')
        print(f'{scan}: frame {top}-{bot} x {xl:.0f}-{xr:.0f} pitch {px:.1f}x{py:.1f}; '
              f'{len(found) - len(diffs)}/{len(found)} agree')
        if diffs:
            print('   ', ' '.join(diffs))
        if a.debug:
            d = im.convert('RGB')
            g = ImageDraw.Draw(d)
            for k in range(int(round((xr - xl) / px)) + 1):
                g.line([(xl + k * px, top), (xl + k * px, bot)], fill=(0, 160, 255), width=2)
            colour = {'circle': (255, 0, 0), 'dot': (0, 170, 0), 'tick': (200, 0, 200)}
            for (kind, ch, box) in found.values():
                if box:
                    g.rectangle(box, outline=colour[kind], width=3)
            out = ROOT / 'work' / 'marks'
            out.mkdir(parents=True, exist_ok=True)
            d.resize((d.width // 2, d.height // 2)).save(out / f'{scan}.png')
    print(f'total {agree}/{total} cells agree')


if __name__ == '__main__':
    main()
