#!/usr/bin/env python3
"""Métricas por ticker para os Grupos (a partir do histórico mensal do Yahoo, range=max, com dividendos e desdobramentos):
ret{n}: variação % do preço em n anos (1..5) · dy{n}: proventos médios por ano nos últimos n anos ÷ preço atual (%)
prov12: proventos 12m ÷ preço (%) + bonificações 12m (%) · anual: proventos por ano (5 anos fechados) ÷ preço médio do ano (%)
ytd: eventos do ano corrente [data, valor/ação, tipo]. Obs.: o Yahoo soma dividendos e JCP (valores brutos) sem distinguir.
Uso: build_metrics.py OUT_DIR  (grava OUT_DIR/metrics.json). DATA_JSON = /api/data local (senão baixa do app)."""
import json, os, sys, time
from datetime import datetime, timezone
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe

out = sys.argv[1]
if os.environ.get("DATA_JSON"):
    rows = json.load(open(os.environ["DATA_JSON"]))["rows"]
else:
    rows = []
    for _ in range(10):
        d = requests.get(os.environ.get("APP_URL", "https://mercado-de-acoes.onrender.com") + "/api/data", timeout=120).json()
        rows = d.get("rows") or []
        if rows:
            break
        time.sleep(20)
kept, _, _ = universe.universe(rows)
now = datetime.now(timezone.utc); Y = now.year
res, fail = {}, 0
for r in kept:
    t = r["ticker"]
    try:
        q = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}.SA", params={"range": "max", "interval": "1mo", "events": "div,split"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=(6, 25))
        q.raise_for_status()
        x = q.json()["chart"]["result"][0]
        pts = [(a, b) for a, b in zip(x.get("timestamp") or [], x["indicators"]["quote"][0]["close"]) if b]
        if len(pts) < 2:
            raise ValueError("vazio")
        ev = x.get("events") or {}
        divs = sorted((int(k), float(v["amount"])) for k, v in (ev.get("dividends") or {}).items())
        spl = sorted((int(k), float(v["numerator"]) / float(v["denominator"])) for k, v in (ev.get("splits") or {}).items() if v.get("denominator"))
        p = pts[-1][1]; tnow = pts[-1][0]
        ftd = (x.get("meta") or {}).get("firstTradeDate") or pts[0][0]
        m = {"p": round(p, 2), "first": datetime.fromtimestamp(pts[0][0], timezone.utc).strftime("%Y-%m"),
             "ftd": datetime.fromtimestamp(ftd, timezone.utc).strftime("%Y-%m-%d"), "m10": [round(c, 2) for _, c in pts[-10:]]}
        for n in range(1, 6):
            old = [c for ts, c in pts if ts <= tnow - n * 365.25 * 86400 + 20 * 86400]
            m[f"ret{n}"] = round((p / old[-1] - 1) * 100, 2) if old else None
            if old:
                s = sum(v for ts, v in divs if ts > tnow - n * 365.25 * 86400)
                m[f"dy{n}"] = round(s / n / p * 100, 2)
        d12 = sum(v for ts, v in divs if ts > tnow - 365.25 * 86400)
        b12 = sum((rt - 1) * 100 for ts, rt in spl if ts > tnow - 365.25 * 86400 and 1 < rt <= 1.5)  # bonificação; acima disso é desdobramento
        m["prov12"] = round(d12 / p * 100 + b12, 2)
        an = {}
        for y in range(Y - 5, Y):
            cl = [c for ts, c in pts if datetime.fromtimestamp(ts, timezone.utc).year == y]
            dv = sum(v for ts, v in divs if datetime.fromtimestamp(ts, timezone.utc).year == y)
            if cl:
                an[str(y)] = round(dv / (sum(cl) / len(cl)) * 100, 3)
        m["anual"] = an
        m["ytd"] = [[datetime.fromtimestamp(ts, timezone.utc).strftime("%m/%Y"), round(v, 4), "provento"] for ts, v in divs if datetime.fromtimestamp(ts, timezone.utc).year == Y] + \
                   [[datetime.fromtimestamp(ts, timezone.utc).strftime("%m/%Y"), round(rt, 4), "bonificação" if 1 < rt <= 1.5 else "desdobramento" if rt > 1 else "grupamento"] for ts, rt in spl if datetime.fromtimestamp(ts, timezone.utc).year == Y]
        res[t] = m
    except Exception as e:
        fail += 1
    time.sleep(0.25)
json.dump({"fetched_at": now.isoformat(), "metrics": res}, open(os.path.join(out, "metrics.json"), "w"), separators=(",", ":"))
print(f"métricas: {len(res)} ok, {fail} falhas")
