"""List the variant (異體) characters of the transcription, for the editor's ruling.

usage: variant_report.py > work/variants_report.md

A character is a candidate when it is outside Big5 (Taiwan's common + less common
characters), when OpenCC's Taiwan-standard conversion changes it, or when it is in
the hand list below. For each: count, current mapping in text/variants.tsv (if any),
and the first places it occurs (scan/column/row).
"""
import sys
from collections import defaultdict
from pathlib import Path

import opencc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pages  # noqa: E402

# common 異體 that are in Big5 all the same
HAND = set('爲眞敎旣卽徧倣着脚叠凄疎踈秘祕緫槩畧竝塡恠徃衆剏剙觔粧牎窓窻鬭闘鬪甞迹亾兎效効强彊纔讐讎'
           '欝衞羣裏峯鷄妬覩')   # only the variant member of each pair


def cells():
    for path in sorted((ROOT / 'text' / 'v1').glob('*.txt')):
        scan = path.stem
        page = gen_pages.parse_page(path)
        for c, (_, items) in enumerate(page.columns, 1):
            for k, it in enumerate(items, 1):
                if it[0] == 'c':
                    yield scan, f'{c}/{k}', it[1]
                elif it[0] == 'n':
                    for half in (it[1], it[2]):
                        for cell in half:
                            if cell[0] == 'c':
                                yield scan, f'{c}/注', cell[1]
        for k, parts in page.notes:
            for part in parts:
                for cell in part:
                    if cell[0] == 'c':
                        yield scan, '眉', cell[1]


def main():
    tw = opencc.OpenCC('t2tw')
    variants = gen_pages.load_variants()
    where = defaultdict(list)
    for scan, pos, ch in cells():
        where[ch].append(f'{scan}:{pos}')
    rows = []
    for ch, places in where.items():
        if ch in '○□':
            continue
        try:
            ch.encode('big5')
            in_big5 = True
        except UnicodeEncodeError:
            in_big5 = False
        tw_form = tw.convert(ch)
        if in_big5 and tw_form == ch and ch not in HAND and ch not in variants:
            continue
        why = []
        if not in_big5:
            why.append('非Big5')
        if tw_form != ch:
            why.append(f'OpenCC→{tw_form}')
        rows.append((-len(places), ch, variants.get(ch, ''), '、'.join(why), places))
    rows.sort()
    print('# 異體字表（待編者裁定）\n')
    print(f'全冊共 {sum(len(p) for p in where.values())} 字，{len(where)} 個不同字；下列 {len(rows)} 個為候選。\n')
    print('| 原刻 | 次數 | 暫定通行字 | 依據 | 出處（掃描:行/字） |')
    print('|---|---|---|---|---|')
    for n, ch, std, why, places in rows:
        more = f' 等 {len(places)} 處' if len(places) > 4 else ''
        print(f'| {ch} | {-n} | {std} | {why} | {" ".join(places[:4])}{more} |')


if __name__ == '__main__':
    main()
