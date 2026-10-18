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

# Série histórica diária (fechamento) dos índices usados como referência nos modelos da Previsão → OUT/b3_idx_hist.json
# Fonte: B3, estatísticas históricas do índice (indexStatisticsProxy/IndexCall/GetPortfolioDay: um ano por pedido, linha = dia,
# rateValue{mês} = fechamento). Anos anteriores ficam do snapshot; refaz o ano corrente e o anterior.
HIST = {"IDIV": 2005}
hp = os.path.join(OUT, "b3_idx_hist.json")
try: hist = json.load(open(hp))["s"]
except Exception: hist = {}
for ix, y0 in HIST.items():
    S = dict(zip(*(hist.get(ix) or {"d": [], "v": []}).values()))
    for y in range(y0, datetime.now().year + 1):
        if y < datetime.now().year - 1 and any(d.startswith(str(y)) for d in S): continue
        p = base64.b64encode(json.dumps({"index": ix, "language": "pt-br", "year": str(y)}).encode()).decode()
        try:
            d = requests.get(f"https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{p}", headers=UA, timeout=30).json()
        except Exception as e:
            print("histórico", ix, y, e, file=sys.stderr); continue
        for r in d.get("results") or []:
            for k, v in r.items():
                if k.startswith("rateValue") and k[9:].isdigit() and v not in (None, ""):
                    try: S[f"{y:04d}-{int(k[9:]):02d}-{int(r['day']):02d}"] = num(v)
                    except (ValueError, KeyError): pass
        time.sleep(0.4)
    if S:
        ks = sorted(S); hist[ix] = {"d": ks, "v": [S[k] for k in ks]}
        print(f"Histórico {ix}: {len(ks)} dias ({ks[0]} a {ks[-1]})")
    else:
        print(f"AVISO: histórico {ix} vazio", file=sys.stderr)
if hist:
    json.dump({"fetched_at": datetime.now().isoformat(timespec="seconds"), "source": "B3 (estatísticas históricas dos índices)", "s": hist},
              open(hp, "w"), separators=(",", ":"))
