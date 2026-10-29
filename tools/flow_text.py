"""Flow the Wikisource text into the measured layout of the original, column by column.

usage: flow_text.py SKELETON.json SECTION.wiki [...] --pages 036-094 [--skip 036:4]
                    [--eval] [--write DIR]

Blocks come from the wikitext: '''◎…''' section titles and '''○…''' 條目 titles are
heading columns, the rest are paragraphs (each starts a new column in the woodblock).
Each measured column (tools/measure_layout.py) has a start row and an occupied length;
its capacity comes from the text's structure: a section's 總論 is 低三格 (17 a
column), 條目 text 頂格 (20) -- some leaves spread the 17 over the whole column, so the
measured start is not reliable for it. A paragraph fills whole
columns; its last column takes what is left. Occupancy is noisy (faint or tiny
characters), so the measured length is used only to check, never to cut text:
  short   the paragraph ends here but the column measured more than one cell longer
  long    the column measured short but the paragraph goes on
  head    a heading column whose length does not match the title
  blank   a blank column inside a paragraph
--eval compares every column with the proofread transcription (text/v1, variants
mapped) and reports exact columns and which flagged columns cover the errors.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pages  # noqa: E402

CJK = re.compile(r'[㐀-鿿\U00020000-\U0002ffff]')


def blocks(paths):
    out = []
    for p in paths:
        t = Path(p).read_text(encoding='utf-8')
        t = re.sub(r'\{\{.*?\}\}', '', t, flags=re.S)
        t = re.sub(r'<[^>]+>|\[\[|\]\]', '', t)
        for line in t.splitlines():
            line = line.strip().strip('　')
            if not line:
                continue
            m = re.fullmatch(r"'''([◎○]?)(.+?)'''", line)
            if m:      # ◎ section title (its 總論 follows, 低三格); ○ 條目 title (頂格 text follows)
                out.append(('sec' if m.group(1) == '◎' else 'item', ''.join(CJK.findall(m.group(2)))))
            else:
                chars = ''.join(CJK.findall(line))
                if chars:
                    out.append(('para', chars))
    return out


def flow(skel, pages, blks, skip):
    """-> {scan: [(start, text, flags)]} for every measured column."""
    result, bi, pos = {}, 0, 0
    width = 17          # this book: a section's 總論 is 低三格 (17 a column), 條目 text 頂格 (20)
    for scan in pages:
        rows = skel[scan]['rows']
        cols = []
        for c, col in enumerate(skel[scan]['cols']):
            if scan in skip and c < skip[scan]:
                cols.append((col['start'], None, []))
                continue
            if bi >= len(blks):
                cols.append((col['start'], '', []))
                continue
            kind, text = blks[bi]
            if col['count'] == 0:
                cols.append((None, '', ['blank'] if kind == 'para' and pos > 0 else []))
                continue
            if kind == 'para' and pos == 0 and col['count'] < 1:
                continue
            flags = []
            if kind in ('sec', 'item'):
                if abs(col['count'] - len(text)) > 0:
                    flags.append('head')
                cols.append((1 if kind == 'sec' else 2, text, flags))
                width = 17 if kind == 'sec' else 20
                bi, pos = bi + 1, 0
                continue
            cap = width          # from the text's structure, not from the (noisy) measurement
            rest = len(text) - pos
            if rest <= cap:
                piece = text[pos:]
                if col['count'] - rest > 1:
                    flags.append('short')
                bi, pos = bi + 1, 0
            else:
                piece = text[pos:pos + cap]
                if col['count'] < cap - 1:
                    flags.append('long')
                pos += cap
            cols.append((3 if width == 17 else 0, piece, flags))
        result[scan] = cols
    return result


# simplified -> traditional conversions that are often wrong (both forms occur in the
# original): every occurrence is listed for a look at the scan
AMBIGUOUS = set('雲云制製發髮盡儘出齣個箇仇讎泄洩托託幸倖恒恆仆僕誌志撲扑弦絃幹干並併葉叶後后淡澹'
                '凈淨醜丑愧媿兇凶粗麤厘釐究窮里裏裡係繫系只隻斗鬥鬭曲麴范範谷穀彩綵准準舍捨')


def write(res, out, skel):
    """Transcription files in the text/v1 format, plus FLAGS.md listing what to check."""
    out.mkdir(parents=True, exist_ok=True)
    flags_md = ['# 待核清單（flow_text.py 生成）\n',
                '每頁：「行 N」為原刻行（自右數）。flags：short/long = 段末行長與原刻量得之長不合（附近多字或缺字）；'
                'head = 標題行長不合；blank = 段中空行。易混字 = 簡轉繁易誤之字，須對圖確認。\n']
    for scan, cols in res.items():
        lines, notes = [], []
        for c, (start, text, flags) in enumerate(cols):
            if text is None:
                lines.append('# 卷首：此行未自動填入，請照原刻錄出')
                continue
            if not text:
                lines.append('')
                continue
            lines.append(f'^{start} {text}')
            amb = [f'{k + 1}{ch}' for k, ch in enumerate(text) if ch in AMBIGUOUS]
            if flags or amb:
                notes.append(f'- 行{c + 1}' + (f' **{",".join(flags)}**' if flags else '')
                             + (f' 易混字（第幾字）：{" ".join(amb)}' if amb else ''))
        while lines and lines[-1] == '':
            lines.pop()
        (out / f'{scan}.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        if notes:
            flags_md.append(f'\n## {scan}\n' + '\n'.join(notes) + '\n')
    (out / 'FLAGS.md').write_text(''.join(flags_md), encoding='utf-8')


def truth_cols(scan, variants):
    page = gen_pages.parse_page(ROOT / 'text' / 'v1' / f'{scan}.txt')
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
    ap.add_argument('skeleton')
    ap.add_argument('wiki', nargs='+')
    ap.add_argument('--pages', required=True)
    ap.add_argument('--skip', default='')
    ap.add_argument('--eval', action='store_true')
    ap.add_argument('--write', help='write transcription files NNN.txt into this directory')
    ap.add_argument('--rules', default='於于,余餘',
                    help='replacements found 100%% regular in this book (卷一): wiki char + original char')
    a = ap.parse_args()
    skel = json.loads(Path(a.skeleton).read_text(encoding='utf-8'))
    p0, p1 = a.pages.split('-')
    pages = [f'{s:03d}' for s in range(int(p0), int(p1) + 1)]
    skip = {k: int(v) for k, v in (x.split(':') for x in a.skip.split(',') if x)}
    rules = dict(r for r in (x.strip() for x in a.rules.split(',')) if len(r) == 2)
    blks = [(k, ''.join(rules.get(ch, ch) for ch in t)) for k, t in blocks(a.wiki)]
    res = flow(skel, pages, blks, skip)
    if a.write:
        write(res, Path(a.write), skel)
    nflag = sum(1 for cols in res.values() for _, _, f in cols if f)
    print(f'{len(pages)} pages, {sum(len(c) for c in res.values())} columns, {nflag} flagged')
    if not a.eval:
        return
    variants = gen_pages.load_variants()
    ncol = exact = flagged_err = err = 0
    first_bad = []
    for scan in pages:
        t = truth_cols(scan, variants)
        for c, (start, text, flags) in enumerate(res[scan]):
            if text is None:
                continue
            want = t[c] if c < len(t) else ''
            ncol += 1
            if text == want:
                exact += 1
            else:
                err += 1
                flagged_err += bool(flags) or any(res[scan][k][2] for k in range(max(0, c - 1), c))
                if len(first_bad) < 12:
                    first_bad.append(f'{scan}/{c + 1} {",".join(flags) or "-"}: got {text[:8]}… want {want[:8]}…')
    print(f'exact columns {exact}/{ncol} ({exact / ncol:.1%}); wrong {err}, of which flagged here or just before {flagged_err}')
    # alignment vs. characters: same length = the column breaks are right
    from collections import Counter
    same_len = chars = diff = 0
    pairs, misaligned = Counter(), []
    for scan in pages:
        t = truth_cols(scan, variants)
        for c, (start, text, flags) in enumerate(res[scan]):
            if text is None:
                continue
            want = t[c] if c < len(t) else ''
            if len(text) == len(want):
                same_len += 1
                for x, y in zip(text, want):
                    chars += 1
                    if x != y:
                        diff += 1
                        pairs[(x, y)] += 1
            else:
                misaligned.append(f'{scan}/{c + 1}{"(" + ",".join(flags) + ")" if flags else ""}')
    print(f'columns of the right length {same_len}/{ncol} ({same_len / ncol:.1%}); misaligned: {" ".join(misaligned[:30])}')
    print(f'characters in aligned columns {chars}, differing {diff} ({diff / max(1, chars):.2%})')
    print('differences (wikisource→original: count):', ' '.join(f'{x}→{y}:{n}' for (x, y), n in pairs.most_common()))


if __name__ == '__main__':
    main()
