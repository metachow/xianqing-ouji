"""Score a v2 transcription (pre-filled from Wikisource, proofread against the scan) against
the proofread v1 transcription, character by character.

usage: eval_v2.py DIR [--pages 036-094]
Both sides are compared as plain text in reading order (variants mapped to standard
characters, marks and 眉批 ignored; the 卷首 lines of the first page are skipped). Reports
remaining differences (errors left or introduced) and column-length agreement.
"""
import argparse
import difflib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import flow_text as ft  # noqa: E402
import gen_pages        # noqa: E402


def cols(path, variants):
    page = gen_pages.parse_page(path)
    out = []
    for _, items in page.columns:
        s = ''
        for it in items:
            if it[0] == 'c':
                s += variants.get(it[1], it[1])
            elif it[0] == 'n':
                s += ''.join(variants.get(c[1], c[1]) for half in it[1:] for c in half if c[0] == 'c')
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--pages', default='036-094')
    a = ap.parse_args()
    v = gen_pages.load_variants()
    p0, p1 = (int(x) for x in a.pages.split('-'))
    got_all, want_all, same_len, ncol = '', '', 0, 0
    for s in range(p0, p1 + 1):
        g = cols(Path(a.dir) / f'{s:03d}.txt', v)
        w = cols(ROOT / 'text' / 'v1' / f'{s:03d}.txt', v)
        if s == p0:          # 卷首: compare from the section title on
            g = g[next(i for i, x in enumerate(g) if '結構' in x):]
            w = w[next(i for i, x in enumerate(w) if '結構' in x):]
        for k in range(max(len(g), len(w))):
            x = g[k] if k < len(g) else ''
            y = w[k] if k < len(w) else ''
            if x or y:
                ncol += 1
                same_len += len(x) == len(y)
        got_all += ''.join(g)
        want_all += ''.join(w)
    sm = difflib.SequenceMatcher(None, got_all, want_all, autojunk=False)
    diffs = Counter()
    n = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal':
            n += max(i2 - i1, j2 - j1)
            diffs[f'{got_all[i1:i2] or "∅"}→{want_all[j1:j2] or "∅"}'] += 1
    print(f'{len(want_all)} characters; differing {n} ({n / len(want_all):.2%}); '
          f'columns of the right length {same_len}/{ncol}')
    print('remaining (v2→v1):', ' '.join(f'{k}:{c}' if c > 1 else k for k, c in diffs.most_common()))


if __name__ == '__main__':
    main()
