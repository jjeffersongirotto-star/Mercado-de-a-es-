"""Volume financeiro médio dos últimos 30 pregões, por ticker (todas as classes), do COTAHIST oficial da B3.
Usado para escolher 1 ticker por empresa (classe mais negociada). Grava OUT/b3_vol30.json.
Uso: build_vol30.py DIR_ZIPS OUT_DIR"""
import io, json, os, sys, time, zipfile, urllib.request
from datetime import datetime
D, OUT = sys.argv[1], sys.argv[2]
Y = datetime.now().year
def zp(y): return os.path.join(D, f"COTAHIST_A{y}.ZIP")
p = zp(Y)
if not os.path.exists(p) or time.time() - os.path.getmtime(p) > 12 * 3600:
    try:
        req = urllib.request.Request(f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{Y}.ZIP", headers={"User-Agent": "Mozilla/5.0"})
        b = urllib.request.urlopen(req, timeout=300).read()
        if len(b) > 1_000_000: open(p + ".tmp", "wb").write(b); os.replace(p + ".tmp", p)
    except Exception as e: print("aviso: download falhou:", e)
rows = {}
for y in (Y - 1, Y):
    if not os.path.exists(zp(y)): continue
    z = zipfile.ZipFile(zp(y))
    for l in io.TextIOWrapper(z.open(z.namelist()[0]), encoding="latin-1"):
        if l[:2] != "01" or l[24:27] != "010" or l[10:12] not in ("02", "12", "14"): continue
        rows.setdefault(l[12:24].strip(), {})[l[2:10]] = int(l[170:188]) / 100
days = sorted({d for v in rows.values() for d in v})[-30:]
v = {t: round(sum(m.get(d, 0) for d in days) / len(days)) for t, m in rows.items() if any(d in m for d in days)}
json.dump({"d": days[-1] if days else None, "v": v}, open(os.path.join(OUT, "b3_vol30.json"), "w"), separators=(",", ":"))
print(len(v), "tickers; último pregão", days[-1] if days else None)
