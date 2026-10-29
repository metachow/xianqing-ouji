"""Picture sheet of every character a proofreader changed, for a quick check by eye.

usage: change_sheet.py BEFORE_DIR AFTER_DIR --pages h053L-h077L [--out work/juan02/changes.png]

Pages are compared column by column (same column count expected; columns whose text
was rewritten as a whole, e.g. re-flowed, are listed but not cut). Each changed
character is cut from the Harvard half-leaf with one cell above and below and labelled
"key/column before→after"; the list is also written next to the sheet as .txt.
"""
import argparse
import difflib
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pages            # noqa: E402
import harvard              # noqa: E402
import measure_layout as ml  # noqa: E402


def columns(path):
    page = gen_pages.parse_page(path)
    out = []
    for start, items in page.columns:
        chars = [it[1] for it in items if it[0] == 'c']
        out.append((start, ''.join(chars)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--pages', required=True)
    ap.add_argument('--out', default='work/changes.png')
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / 'text' / 'layout.yaml').read_text(encoding='utf-8'))
    try:
        font = ImageFont.truetype(str(ROOT / 'fonts' / 'NotoSerifTC-Regular.otf'), 14)
    except OSError:
        font = None
    tiles, lines = [], []
    for key in gen_pages.page_range(a.pages, cfg):
        b, f = ROOT / a.before / f'{key}.txt', ROOT / a.after / f'{key}.txt'
        if not (b.exists() and f.exists()):
            continue
        cb, ca = columns(b), columns(f)
        lay = cfg['layouts'][cfg['pages'][key]['layout']]
        grid = None
        for c in range(max(len(cb), len(ca))):
            sb = cb[c][1] if c < len(cb) else ''
            start, sa = ca[c] if c < len(ca) else (None, '')
            if sb == sa:
                continue
            ops = [o for o in difflib.SequenceMatcher(None, sb, sa, autojunk=False).get_opcodes() if o[0] != 'equal']
            if sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in ops) > 6:
                lines.append(f'{key} 行{c + 1}: rewritten  {sb} → {sa}')
                continue
            if grid is None:
                ink, box, top, px, py, xr, ncol, nrow = ml.grid(key, cfg)
                im = harvard.half(key).convert('L')
                grid = True
            r0 = lay['indent'] if start is None else start
            for op, i1, i2, j1, j2 in ops:
                lines.append(f'{key} 行{c + 1} 字{j1 + 1}: {sb[i1:i2] or "∅"} → {sa[j1:j2] or "∅"}')
                row = r0 + j1
                cx = xr - (c + 0.5) * px
                t = im.crop((int(cx - 0.6 * px), int(top + (row - 1) * py), int(cx + 0.6 * px), int(top + (row + 2) * py)))
                t = t.resize((140, round(140 * t.height / t.width)))
                cv = Image.new('L', (140, t.height + 22), 255)
                cv.paste(t, (0, 22))
                ImageDraw.Draw(cv).text((3, 2), f'{key}/{c + 1} {sb[i1:i2] or "∅"}→{sa[j1:j2] or "∅"}', fill=0, font=font)
                tiles.append(cv)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix('.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if tiles:
        per = 12
        h = max(t.height for t in tiles)
        sheet = Image.new('L', (per * 146, ((len(tiles) + per - 1) // per) * (h + 6)), 128)
        for i, t in enumerate(tiles):
            r, c = divmod(i, per)
            sheet.paste(t, (c * 146, r * (h + 6)))
        sheet.save(out)
    print(f'{len(tiles)} changed characters cut, {len(lines)} changes listed -> {out}')


if __name__ == '__main__':
    main()
