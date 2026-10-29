"""Download the fonts into fonts/ (not kept in the repository).

usage: fetch_fonts.py
- Noto Serif TC (OFL), static OTF cuts from notofonts/noto-cjk release Serif2.003
  (15_NotoSerifTC.zip, SubsetOTF/TC): Regular, Medium, SemiBold, Bold.
- 全字庫正楷體 TW-Kai and 全字庫正宋體 TW-Sung (Taiwan's CNS 11643 open data, 政府資料開放授權條款),
  BMP files only, saved as TW-Kai.ttf and TW-Sung.ttf.
The archives are large (Noto ~250 MB, each 全字庫 ~60 MB).
"""
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'fonts'
NOTO = 'https://github.com/notofonts/noto-cjk/releases/download/Serif2.003/15_NotoSerifTC.zip'
CNS = {'TW-Kai.ttf': ('https://www.cns11643.gov.tw/opendata/Fonts_Kai.zip', 'TW-Kai-98_1.ttf'),
       'TW-Sung.ttf': ('https://www.cns11643.gov.tw/opendata/Fonts_Sung.zip', 'TW-Sung-98_1.ttf')}


def fetch(url, dest):
    print('downloading', url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, 'wb') as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


OUT.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    want = [f'NotoSerifTC-{w}.otf' for w in ('Regular', 'Medium', 'SemiBold', 'Bold')]
    if not all((OUT / w).exists() for w in want):
        z = Path(tmp) / 'noto.zip'
        fetch(NOTO, z)
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                if Path(name).name in want:
                    (OUT / Path(name).name).write_bytes(zf.read(name))
    for target, (url, member) in CNS.items():
        if (OUT / target).exists():
            continue
        z = Path(tmp) / 'cns.zip'
        fetch(url, z)
        with zipfile.ZipFile(z) as zf:
            (OUT / target).write_bytes(zf.read(member))
print('fonts:', ', '.join(sorted(p.name for p in OUT.glob('*.[ot]tf'))))
