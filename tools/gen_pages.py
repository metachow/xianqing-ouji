"""Generate one TikZ page per scan from the transcription.

usage: gen_pages.py [SCAN ...]

Without arguments: every page in text/layout.yaml, plus pages/list.tex (the \\input
list for main.tex) and work/variants_applied.tsv (every character changed by
text/variants.tsv, for the textual notes). With scan numbers: only those pages
(safe to run in parallel). Never edit the generated files; edit text/ and rerun.

Transcription format: see work/TRANSCRIPTION.md. One line per column, right to left:
  。 、 •   circle / tick / filled dot at the lower right of the preceding character
  { }      dense circles on every character inside (within one page only: a page
           that starts inside such a passage starts with '{')
  〔右|左〕 double-line small note (割注): right and left half-columns
  　       (full-width space) an empty cell
  ^N       at the start of a line: the column starts at row N (default: layout
           indent); negative = raised above the frame (抬頭)
  @眉 K a|b|c   marginal note above the frame, first column over column K
  @版心 X|Y     override the 版心 section label and leaf number
  #        comment
"""
import math
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / 'text'
OUT = ROOT / 'pages'

# geometry in mm, measured on the scans (300 dpi): page = scan size
PAGE_W, PAGE_H = 160.9, 254.0
FRAME_TOP = 38.0            # from the top of the page
FRAME_H = 184.0
TEXT_W = 120.0              # width of the text area (all columns)
BANXIN_W = 21.0             # half of the 版心 strip, at the fore-edge
BORDER = 0.9                # thick frame line
RULE = 0.28                 # column rule
PT = 2.845                  # pt per mm

MEIPI = dict(size=4.6, row=5.6, pitch=9.0, gap=2.2)   # 眉批: glyph, row pitch, column pitch, gap above frame
BANXIN = dict(size=5.6, row=6.6)

MARKS = {'。': 'circle', '、': 'tick', '•': 'dot'}


def load_variants():
    table = {}
    for line in (TEXT / 'variants.tsv').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        orig, std, *_ = line.split('\t')
        table[orig] = std
    return table


class Page:
    def __init__(self):
        self.columns = []    # (start_row or None, items)
        self.notes = []      # (column, [cells per note column])
        self.banxin = None   # (label, leaf) override
        self.placed = []     # (column position, start row, cells) placed freely
        self.norule = set()  # K: no rule between columns K and K+1


def parse_page(path):
    page = Page()
    emph = False
    for n, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.rstrip()
        try:
            if line.startswith('#'):
                continue
            if line.startswith('@眉'):
                _, k, body = line.split(None, 2)
                page.notes.append((int(k), [parse_items(part, False)[0] for part in body.split('|')]))
                continue
            if line.startswith('@位'):
                _, x, y, body = line.split(None, 3)
                page.placed.append((float(x), float(y), parse_items(body, False)[0]))
                continue
            if line.startswith('@無界'):
                page.norule.update(int(k) for k in line.split()[1:])
                continue
            if line.startswith('@版心'):
                label, leaf = line.split(None, 1)[1].split('|')
                page.banxin = (label.strip(), leaf.strip())
                continue
            if line.startswith('@'):
                raise ValueError(f'unknown directive {line.split()[0]}')
            start = None
            if line.startswith('^'):
                m = 1
                while m < len(line) and (line[m].isdigit() or (m == 1 and line[m] == '-')):
                    m += 1
                start, line = int(line[1:m]), line[m:].lstrip(' ')
            items, emph = parse_items(line, emph)
            page.columns.append((start, items))
        except ValueError as e:
            raise ValueError(f'{path.name} line {n}: {e}') from None
    return page


def parse_items(s, emph):
    """Items: ('c', char, mark) | ('e',) | ('n', right_cells, left_cells)."""
    items, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == '{':
            emph = True
        elif ch == '}':
            emph = False
        elif ch in MARKS:
            if not items or items[-1][0] != 'c':
                raise ValueError(f'mark {ch} without a character before it')
            items[-1] = ('c', items[-1][1], MARKS[ch])
        elif ch == '　':
            items.append(('e',))
        elif ch == '〔':
            j = s.find('〕', i)
            if j < 0:
                raise ValueError('〔 without 〕')
            parts = s[i + 1:j].split('|')
            if len(parts) > 2:
                raise ValueError('a double-line note has at most two halves')
            halves = []
            for part in parts:
                cells, emph = parse_items(part, emph)
                if any(c[0] == 'n' for c in cells):
                    raise ValueError('nested note')
                halves.append(cells)
            items.append(('n', halves[0], halves[1] if len(halves) > 1 else []))
            i = j
        elif ch in '〕|':
            raise ValueError(f'stray {ch}')
        elif ch in ' \t':
            raise ValueError('ASCII space in text (use 　 for an empty cell)')
        else:
            items.append(('c', ch, 'circle' if emph else None))
        i += 1
    return items, emph


def column_rows(items, note_pitch):
    rows = 0.0
    for it in items:
        rows += max(len(it[1]), len(it[2])) * note_pitch if it[0] == 'n' else 1
    return rows


def node(x, y, ch, family, size_mm):
    pt = size_mm * PT
    return (f'\\node[inner sep=0pt,anchor=center] at ({x:.2f}mm,{y:.2f}mm) '
            f'{{\\fontsize{{{pt:.2f}pt}}{{{pt:.2f}pt}}\\{family} {ch}}};\n')


SHOW_MARKS = True       # layout.yaml show_marks: false hides the (not yet verified) 圈點


def load_jiaoji_index():
    """scan -> [(k, column)] for the 校記 entries (target jj-k, see gen_appendix.py)."""
    index = {}
    path = TEXT / 'jiaoji.yaml'
    if path.exists():
        for k, e in enumerate(yaml.safe_load(path.read_text(encoding='utf-8')), 1):
            index.setdefault(e['scan'], []).append((k, e['col']))
    return index


JIAOJI = load_jiaoji_index()


def load_mark_layer(name):
    """(scan, column, item) -> mark from a mark layer such as text/marks_wikisource.tsv."""
    layer = {}
    path = TEXT / f'marks_{name}.tsv'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line and not line.startswith('#'):
                scan, col, item, _, mk = line.split('\t')
                layer[(scan, int(col), int(item))] = mk
    return layer


MARK_LAYERS = {}   # layout `marks:` value -> layer, loaded on first use


def mark(x, y, kind, scale):
    """A punctuation mark centred at (x, y); scale ~ glyph size in mm / 7.4."""
    if not SHOW_MARKS:
        return ''
    if kind == 'circle':
        return f'\\draw[line width={0.24*scale:.2f}mm] ({x:.2f}mm,{y:.2f}mm) circle ({0.95*scale:.2f}mm);\n'   # ~1.8 mm across, as cut
    if kind == 'dot':
        return f'\\fill ({x:.2f}mm,{y:.2f}mm) circle ({0.80*scale:.2f}mm);\n'
    if kind == 'tick':
        return (f'\\draw[line width={0.42*scale:.2f}mm,line cap=round] '
                f'({x-0.35*scale:.2f}mm,{y+0.55*scale:.2f}mm) -- ({x+0.3*scale:.2f}mm,{y-0.5*scale:.2f}mm);\n')
    raise ValueError(kind)


def render(scan, info, lay, page, variants, applied):
    side = info['side']
    if side == 'a':     # recto: 版心 at the left edge, binding margin at the right
        bx0, tx0 = 0.0, BANXIN_W
    else:               # verso: binding margin at the left, 版心 at the right edge
        tx0 = PAGE_W - BANXIN_W - TEXT_W
        bx0 = tx0 + TEXT_W
    tx1 = tx0 + TEXT_W
    top = PAGE_H - FRAME_TOP
    bot = top - FRAME_H
    ncol, nrow = lay['cols'], lay['rows']
    pitch_x, pitch_y = TEXT_W / ncol, FRAME_H / nrow
    glyph = lay['size'] * pitch_y
    small = lay.get('note_size', 0.62) * glyph
    note_pitch = lay.get('note_pitch', 0.62)
    sc = glyph / 7.4
    out = [f'% generated by tools/gen_pages.py from text/v1/{scan}.txt -- do not edit\n',
           '\\begin{tikzpicture}[remember picture,overlay,shift={(current page.south west)},xshift=\\edxshift]\n']

    if len(page.columns) > ncol:
        raise ValueError(f'{scan}: {len(page.columns)} columns, layout {info["layout"]} has {ncol}')
    starts = [lay['indent'] if s is None else s for s, _ in page.columns]
    raised = {c: -s for c, s in enumerate(starts) if s < 0}     # 抬頭: column -> rows above the frame

    def col_x(c):
        return tx1 - (c + 0.5) * pitch_x

    # frame: thick top and bottom across text area and 版心, thick outer edge;
    # the top line steps up over raised columns
    x_left, x_right = (bx0, tx1) if side == 'a' else (tx0, PAGE_W)
    pts = [(x_right, top), (tx1, top)]         # walk right to left along the top line
    for c in range(ncol):
        h = top + raised.get(c, 0) * pitch_y
        pts += [(tx1 - c * pitch_x, h), (tx1 - (c + 1) * pitch_x, h)]
    pts.append((tx0, top))
    pts.append((x_left, top))
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    path = ' -- '.join(f'({px:.2f}mm,{py:.2f}mm)' for px, py in pts)
    out.append(f'\\draw[line width={BORDER}mm,line join=miter] {path};\n')
    out.append(f'\\draw[line width={BORDER}mm] ({x_left:.2f}mm,{bot:.2f}mm) -- ({x_right:.2f}mm,{bot:.2f}mm);\n')
    outer = tx1 if side == 'a' else tx0
    out.append(f'\\draw[line width={BORDER}mm] ({outer:.2f}mm,{top+BORDER/2:.2f}mm) -- ({outer:.2f}mm,{bot-BORDER/2:.2f}mm);\n')
    for k in range(ncol + 1):
        x = tx0 + k * pitch_x
        if abs(x - outer) < 0.01 or (ncol - k) in page.norule:
            continue
        # a rule beside a raised column rises with it
        c_left, c_right = ncol - k, ncol - k - 1           # columns left and right of this rule
        h = top + max(raised.get(c_left, 0), raised.get(c_right, 0)) * pitch_y
        out.append(f'\\draw[line width={RULE}mm] ({x:.2f}mm,{h:.2f}mm) -- ({x:.2f}mm,{bot:.2f}mm);\n')

    # 版心: book title, section, leaf number
    label, leaf = page.banxin or (info['juan'], str(info['leaf']))
    bxc = bx0 + BANXIN_W / 2
    y = top - 1.2 - BANXIN['row'] / 2
    for ch in '閒情偶寄':
        out.append(node(bxc, y, ch, 'song', BANXIN['size']))
        y -= BANXIN['row']
    y -= 2.5
    for ch in label:
        out.append(node(bxc, y, ch, 'song', BANXIN['size']))
        y -= BANXIN['row']
    y = top - 0.62 * FRAME_H
    for ch in leaf:
        out.append(node(bxc, y, ch, 'song', BANXIN['size']))
        y -= BANXIN['row']

    def put(x, y, ch, mk, size, family, where):
        std = variants.get(ch, ch)
        if std != ch:
            applied.append((scan, *where, ch, std))
        s = size / 7.4
        out.append(node(x, y, std, family, size))
        return s

    # which marks to draw on the main text: the transcription's own (default), or a
    # separate layer named by the layout (`marks: wikisource` -> text/marks_wikisource.tsv)
    source = lay.get('marks', 'transcribed')
    if source != 'transcribed' and source not in MARK_LAYERS:
        MARK_LAYERS[source] = load_mark_layer(source)
    layer = MARK_LAYERS.get(source)

    # text columns, right to left
    for c, ((_, items), r0) in enumerate(zip(page.columns, starts)):
        x = col_x(c)
        used = column_rows(items, note_pitch)
        if r0 + used > nrow + 1e-6:
            raise ValueError(f'{scan} column {c+1}: {used:g} rows from row {r0} > {nrow}')
        r = float(r0)
        for k_item, it in enumerate(items, 1):
            if it[0] == 'e':
                r += 1
                continue
            if it[0] == 'c':
                y = top - (r + 0.5) * pitch_y
                put(x, y, it[1], it[2], glyph, lay['font'], (c + 1, math.floor(r) + 1))
                mk = it[2] if layer is None else layer.get((scan, c + 1, k_item))
                if mk:      # in the gutter, next to the column rule, at the lower part of the glyph
                    out.append(mark(x + 0.44 * pitch_x, y - 0.32 * glyph, mk, 0.9 * min(sc, 1.25)))
                r += 1
                continue
            # double-line note: two half-columns of small characters
            for half, cells in ((0, it[1]), (1, it[2])):
                hx = x + (0.22 if half == 0 else -0.22) * pitch_x
                for k, cell in enumerate(cells):
                    if cell[0] != 'c':          # empty small cell
                        continue
                    _, ch, mk = cell
                    y = top - (r + (k + 0.5) * note_pitch) * pitch_y
                    put(hx, y, ch, mk, small, lay['font'], (c + 1, math.floor(r + k * note_pitch) + 1))
                    if mk:
                        out.append(mark(hx + 0.2 * pitch_x, y - 0.32 * small, mk, 0.8 * small / 7.4))
            r += max(len(it[1]), len(it[2])) * note_pitch

    # freely placed text (e.g. names set between two columns): column position may be
    # fractional (2.5 = on the rule between columns 2 and 3), rows too
    for cpos, r0, cells in page.placed:
        x = tx1 - (cpos - 0.5) * pitch_x
        for k, cell in enumerate(cells):
            if cell[0] != 'c':
                continue
            y = top - (r0 + k + 0.5) * pitch_y
            put(x, y, cell[1], cell[2], glyph, lay['font'], (f'位{cpos:g}', math.floor(r0 + k) + 1))

    # an invisible link over each column that has a 校記 entry, back to the entry
    # (xdvipdfmx sizes \hyperlink areas by what is drawn, so give the rectangle explicitly)
    for k, col in JIAOJI.get(scan, []):
        out.append(f'\\node[inner sep=0pt] at ({col_x(col - 1) - pitch_x / 2:.2f}mm,{top:.2f}mm) '
                   f'{{\\special{{pdf:ann width {pitch_x:.2f}mm height 0pt depth {FRAME_H:.2f}mm '
                   f'<</Type/Annot/Subtype/Link/Border[0 0 0]/A<</S/GoTo/D(jj-{k})>>>>}}}};\n')

    # 眉批 above the frame
    for k, parts in page.notes:
        rows = max(len(p) for p in parts)
        for j, cells in enumerate(parts):
            x = col_x(k - 1) - j * MEIPI['pitch']
            for r, it in enumerate(cells):
                if it[0] != 'c':
                    continue
                y = top + MEIPI['gap'] + (rows - r - 0.5) * MEIPI['row']
                put(x, y, it[1], it[2], MEIPI['size'], 'song', (f'眉{j+1}', r + 1))
                if it[2]:
                    s = MEIPI['size'] / 7.4
                    out.append(mark(x + MEIPI['size'] / 2 + 0.9 * s, y - 0.28 * MEIPI['size'], it[2], s * 0.9))
    out.append('\\end{tikzpicture}\n')
    return ''.join(out)


def spread_listing(cfg):
    """\\input list of openings for main_spread.tex: the cover alone, then pairs of a b side
    (right half) and the following a side (left half); a side without a partner gets an
    empty half. Bookmarks go before the opening that holds their page."""
    pages = list(cfg['pages'])          # the order of layout.yaml
    marks = cfg.get('bookmarks', {})
    out, i = [], 0

    def bm(scans):
        return ''.join(f'\\edbookmark{{{lv}}}{{{t}}}\n' for s in scans for lv, t in marks.get(s, []))

    while i < len(pages):
        s = pages[i]
        info = cfg['pages'][s]
        if info['layout'] == 'cover':
            out.append(bm([s]) + f'\\edsingle{{{s}}}\n')
            i += 1
        elif info['side'] == 'b' and i + 1 < len(pages) and cfg['pages'][pages[i + 1]]['side'] == 'a':
            out.append(bm([s, pages[i + 1]]) + f'\\edspread{{{s}}}{{{pages[i + 1]}}}\n')
            i += 2
        elif info['side'] == 'b':
            out.append(bm([s]) + f'\\edspread{{{s}}}{{}}\n')
            i += 1
        else:
            out.append(bm([s]) + f'\\edspread{{}}{{{s}}}\n')
            i += 1
    return ''.join(out)


def main():
    global SHOW_MARKS
    cfg = yaml.safe_load((TEXT / 'layout.yaml').read_text(encoding='utf-8'))
    SHOW_MARKS = cfg.get('show_marks', True)
    variants = load_variants()
    wanted = {f'{int(s):03d}' for s in sys.argv[1:]}
    OUT.mkdir(exist_ok=True)
    applied, listing, missing = [], [], []
    for scan in cfg['pages']:           # the order of layout.yaml (= binding order)
        info = cfg['pages'][scan]
        if wanted and scan not in wanted:
            continue
        for level, title in cfg.get('bookmarks', {}).get(scan, []):
            listing.append(f'\\edbookmark{{{level}}}{{{title}}}\n')
        listing.append(f'\\edpage{{{scan}}}\n')
        special = {'cover': '\\input{front/cover}\n', 'coverin': '\\input{front/cover_inside}\n',
                   'title': '\\input{front/title}\n',
                   'blank': '% blank side of a leaf (not scanned in the PKU copy)\n'}
        if info['layout'] in special:
            (OUT / f'{scan}.tex').write_text(special[info['layout']], encoding='utf-8')
            continue
        src = TEXT / 'v1' / f'{scan}.txt'
        if src.exists():
            page = parse_page(src)
        else:
            page = Page()
            missing.append(scan)
        tex = render(scan, info, cfg['layouts'][info['layout']], page, variants, applied)
        (OUT / f'{scan}.tex').write_text(tex, encoding='utf-8')
    if not wanted:
        (OUT / 'list.tex').write_text(''.join(listing), encoding='utf-8')
        (OUT / 'list_spread.tex').write_text(spread_listing(cfg), encoding='utf-8')
        with open(ROOT / 'work' / 'variants_applied.tsv', 'w', encoding='utf-8') as f:
            f.write('scan\tcolumn\trow\toriginal\tstandard\n')
            for row in applied:
                f.write('\t'.join(map(str, row)) + '\n')
    print(f'{len(listing)} pages, {len(applied)} variant replacements'
          + (f', not yet transcribed: {" ".join(missing)}' if missing else ''))


if __name__ == '__main__':
    main()
