"""Download the Wikisource text of 閑情偶寄 used for cross-checking and for 卷一's 句讀.

usage: fetch_wikisource.py
Writes text/wikisource/<page>.wiki (wikitext). Wikisource content is CC BY-SA 4.0; it was
converted from simplified characters and has errors, so it serves as a cross-check
and as the source of the 句讀 layer (tools/wiki_punct.py), never as the base text.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ['序', '詞曲部', '詞曲部/結構第一', '詞曲部/詞采第二', '詞曲部/音律第三',
         '詞曲部/賓白第四', '詞曲部/科諢第五', '詞曲部/格局第六',   # 填詞餘論 is inside 格局第六
         '演習部', '演習部/選劇第一', '演習部/變調第二']
S2T = {'演習部/選劇第一'}   # these Wikisource pages are in simplified characters: OpenCC s2tw on download
API = 'https://zh.wikisource.org/w/api.php?action=parse&prop=wikitext&format=json&formatversion=2&page='

out = ROOT / 'text' / 'wikisource'
out.mkdir(parents=True, exist_ok=True)
for p in PAGES:
    f = out / (p.replace('/', '_') + '.wiki')
    if f.exists():          # already fetched; Wikisource answers 429 to quick repeats
        continue
    time.sleep(5)
    url = API + urllib.parse.quote('閑情偶寄/' + p)
    req = urllib.request.Request(url, headers={'User-Agent': 'xianqing-ouji edition (github.com/metachow)'})
    for wait in (60, 180, 600, None):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = json.load(r)['parse']['wikitext']
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            print('429, retrying in', wait, 's')
            time.sleep(wait)
    if p in S2T:
        import opencc
        text = opencc.OpenCC('s2tw').convert(text)   # Taiwan standard forms (為, not 爲)
    f.write_text(text, encoding='utf-8')
    print(f.relative_to(ROOT), len(text))
