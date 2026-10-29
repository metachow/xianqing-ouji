"""Download the Wikisource text of 閑情偶寄 used for cross-checking and for 卷一's 句讀.

usage: fetch_wikisource.py
Writes text/wikisource/<page>.wiki (wikitext). Wikisource content is CC BY-SA 4.0; it was
converted from simplified characters and has errors, so it serves as a cross-check
and as the source of the 句讀 layer (tools/wiki_punct.py), never as the base text.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ['序', '詞曲部', '詞曲部/結構第一', '詞曲部/詞采第二', '詞曲部/音律第三',
         '詞曲部/賓白第四', '詞曲部/科諢第五', '詞曲部/格局第六']   # 填詞餘論 is inside 格局第六
API = 'https://zh.wikisource.org/w/api.php?action=parse&prop=wikitext&format=json&formatversion=2&page='

out = ROOT / 'text' / 'wikisource'
out.mkdir(parents=True, exist_ok=True)
for p in PAGES:
    url = API + urllib.parse.quote('閑情偶寄/' + p)
    req = urllib.request.Request(url, headers={'User-Agent': 'xianqing-ouji edition (github.com/metachow)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = json.load(r)['parse']['wikitext']
    f = out / (p.replace('/', '_') + '.wiki')
    f.write_text(text, encoding='utf-8')
    print(f.relative_to(ROOT), len(text))
