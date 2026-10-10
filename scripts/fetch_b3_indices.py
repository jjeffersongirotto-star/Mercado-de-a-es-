#!/usr/bin/env python3
"""Composição oficial dos índices da B3 (carteira do dia, participação %) → OUT/b3_indices.json + OUT/b3_indices/AAAA-MM-DD.json.
Fonte: sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay. Dados da B3 têm prioridade sobre outras fontes."""
import base64, json, os, sys, time
from datetime import datetime
import requests

OUT = sys.argv[1]
IDX = ["IBOV", "IBXX", "IBXL", "IBRA", "SMLL", "MLCX", "IDIV", "IFIX", "IGCX", "ITAG", "IGNM", "ISEE", "ICO2", "UTIL", "IFNC", "IMAT", "INDX", "ICON", "IEEX", "IMOB", "AGFS", "BDRX"]
UA = {"User-Agent": "Mozilla/5.0"}
num = lambda s: float(str(s).replace(".", "").replace(",", ".")) if s not in (None, "") else None
res, date = {}, None
for ix in IDX:
    comp, pg = {}, 1
    while True:
        p = base64.b64encode(json.dumps({"language": "pt-br", "pageNumber": pg, "pageSize": 200, "index": ix, "segment": "1"}).encode()).decode()
        try:
            d = requests.get(f"https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/{p}", headers=UA, timeout=30).json()
        except Exception as e:
            print("índice", ix, e, file=sys.stderr); break
        for r in d.get("results") or []:
            comp[r["cod"].strip()] = num(r.get("part"))
        date = date or (d.get("header") or {}).get("date")
        if pg >= ((d.get("page") or {}).get("totalPages") or 1):
            break
        pg += 1
    if comp:
        res[ix] = comp
    time.sleep(0.4)
day = datetime.strptime(date, "%d/%m/%y").strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")
pay = {"date": day, "fetched_at": datetime.now().isoformat(timespec="seconds"), "source": "B3 (carteira do dia)", "indices": res}
os.makedirs(os.path.join(OUT, "b3_indices"), exist_ok=True)
for f in (os.path.join(OUT, "b3_indices.json"), os.path.join(OUT, "b3_indices", day + ".json")):
    json.dump(pay, open(f, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"Índices B3: {len(res)} índices, carteira de {day}")
